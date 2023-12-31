from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import render
from django.urls import reverse
from django import forms
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import decimal
import pytz


from .models import User, AuctionListing, Bid, Comment, Category, get_default_end_datetime

DEFAULT_IMG = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Placeholder_view_vector.svg/310px-Placeholder_view_vector.svg.png"


class NewAuctionForm(forms.Form):
    title = forms.CharField(label="Title", max_length=255)
    description = forms.CharField(label="Description", widget=forms.Textarea)
    end_datetime = forms.DateTimeField(initial=get_default_end_datetime)
    initial_price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, initial=0.00, required=True)
    image_url = forms.URLField(label="Auction image URL", required=False, empty_value=DEFAULT_IMG)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), empty_label="--None--", required=False)
    
    def clean_initial_price(self):
        initial_price = self.cleaned_data.get('initial_price')
        if initial_price is None or initial_price <= 0:
            raise forms.ValidationError('Initial price must be greater than 0')
        return initial_price

class NewCommentForm(forms.Form):
    comment_text = forms.CharField(label="Add a new comment", widget=forms.Textarea)

class NewBidForm(forms.Form):
    amount = forms.DecimalField()

    # Modified __init__ to add dynamic min and initial value
    # Code by: my favourite rubber duck <3
    def __init__(self, *args, **kwargs):
        self.min_amount = kwargs.pop('min_amount', None)
        super(NewBidForm, self).__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if self.min_amount is not None and amount <= self.min_amount:
            raise ValidationError('Your bid must be greater than the current price.')
        return amount


@login_required
def new(request):
    if request.method == "POST":
        # Save the data as form
        form = NewAuctionForm(request.POST)

        # Check if data is valid
        if form.is_valid():
            # Add the new auction list to the DB
            al = AuctionListing(
                title=form.cleaned_data["title"], 
                description=form.cleaned_data["description"], 
                listed_by=request.user, 
                datetime_listed=datetime.now(pytz.UTC), 
                end_datetime=form.cleaned_data["end_datetime"],
                initial_price=form.cleaned_data["initial_price"],
                image_url=form.cleaned_data["image_url"],
                category=form.cleaned_data["category"]
            )
            al.save()

            # Redirect user to list of tasks
            return HttpResponseRedirect(reverse("index"))

        else:
            # If the form is invalid, re-render the page with a message.
            return render(request, "auctions/new.html", {
                "form": form,
                "message": "Error: invalid input"
            })

    else:
        return render(request, "auctions/new.html", {
            "form": NewAuctionForm()
        })


def listings(request, id):
    try:
        listing = AuctionListing.objects.get(id=id)
    except ObjectDoesNotExist:
        # Renders an error if listing id doesn't exists
        return render(request, "auctions/listings.html", {
            "message": "Error 404: Listing doesn't exists"
        })
    
    # Add or remove user to watchers when button clicked
    if request.GET.get('watch') == "true":
        listing.watchers.add(request.user)
        listing.save()
        return HttpResponseRedirect(request.path_info)
    elif request.GET.get('watch') == "false":
        listing.watchers.remove(request.user)
        listing.save()
        return HttpResponseRedirect(request.path_info)
    
    # Validates new Bid and insert in DB
    if request.POST.get('amount'):
        form = NewBidForm(
            min_amount=decimal.Decimal(listing.current_price), 
            initial={'amount': decimal.Decimal(listing.current_price)},
            data=request.POST
        )

        # Check if data is valid
        if form.is_valid():
            # Add the new bid to the DB
            bid = Bid(
                user = request.user,
                auction = listing,
                amount = form.cleaned_data["amount"]
            )
            bid.save()

            return HttpResponseRedirect(request.path_info)
        else:
            # Renders an error if invalid bid
            return render(request, "auctions/listings.html", {
                "listing": listing,
                "comments": listing.comments.all().order_by('-datetime_commented'),
                "new_comment": NewCommentForm(),
                "new_bid": NewBidForm(
                    min_amount= decimal.Decimal(listing.current_price), 
                    initial={'amount': decimal.Decimal(listing.current_price)
                }),
                "message": "Error: Invalid bid amount"
            })
            
        
    # Unlist Auction and determine winner
    if request.GET.get('unlist') == "true" and request.user == listing.listed_by:
        # Changing end date_time to present time to finish the auction
        listing.end_datetime = datetime.now(pytz.UTC)
        listing.save()
        return HttpResponseRedirect(request.path_info)
    
    # Handle new message form
    if request.POST.get('comment_text'):
        # Save the data as form
        form = NewCommentForm(request.POST)

        # Check if data is valid
        if form.is_valid():
            # Add the new comment to the DB
            comment = Comment(
                commented_by= request.user,
                auction = listing,
                datetime_commented = datetime.now(pytz.UTC),
                comment_text = form.cleaned_data["comment_text"]
            )
            comment.save()

    # Render listing page with details
    return render(request, "auctions/listings.html", {
        "listing": listing,
        "comments": listing.comments.all().order_by('-datetime_commented'),
        "new_comment": NewCommentForm(),
        "new_bid": NewBidForm(
            min_amount= decimal.Decimal(listing.current_price), 
            initial={'amount': decimal.Decimal(listing.current_price)
        })
    })


@login_required
def watchlist(request):
    # Renders all listings in your watchlist
    listings = AuctionListing.objects.filter(watchers=request.user)
    return render(request, "auctions/index.html", {
        "listings": listings,
        "title": "Watchlist"
    })


def index(request):
    # Filter auction listings by active (before end time passes)
    listings = AuctionListing.objects.filter(end_datetime__gt=timezone.now())

    return render(request, "auctions/index.html", {
        "listings": listings,
        "title": "Active listings"
    })


def categories(request, category='all'):
    try:
        if category == 'all':
            # Get all categories
            categories = Category.objects.all().order_by("-name")
            # Render all categories
            return render(request, "auctions/categories.html", {
                "categories": categories
            })
        else:
            # Get category object
            cat = Category.objects.get(name=category)
            # Get all auction listings where category match and are active
            listings = AuctionListing.objects.filter(category=cat.id, end_datetime__gt=timezone.now())
            # Render all listings of current category
            return render(request, "auctions/index.html", {
                "listings": listings,
                "category": category,
                "title": "Active listings"
            })
    except:
        return render(request, "auctions/index.html", {
            "listings": None,
            "message": "Error 404: Category not found"
        })


def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "auctions/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "auctions/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "auctions/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "auctions/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "auctions/register.html")
