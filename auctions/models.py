from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import timedelta, datetime
import pytz

def get_default_end_datetime():
    return datetime.now(pytz.UTC) + timedelta(weeks=1)

class User(AbstractUser):
    # If i need or want can add some fields to this model
    # TODO: Maybe I can show more info in the /admin models tables 
    pass

class AuctionListing(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    listed_by = models.ForeignKey("User", on_delete=models.CASCADE)
    datetime_listed = models.DateTimeField(auto_now_add=True)
    # Auction end date is one week later by default 
    end_datetime = models.DateTimeField(default=get_default_end_datetime, blank=True, null=True)
    initial_price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField()
    category = models.ForeignKey("Category", on_delete=models.SET_NULL, null=True, blank=True)
    watchers = models.ManyToManyField("User", related_name="watchlist", blank=True)
    winner = models.ForeignKey("User", on_delete=models.SET_NULL, null=True, blank=True, related_name="won_auctions")

    def __str__(self):
        return self.title
    
    # When looking at auction details check this function to show the winner if not active
    @property
    def is_active(self):
        return self.end_datetime > datetime.now(pytz.UTC)
    
    @property
    def current_price(self):
        if self.current_highest_bid is None:
            return self.initial_price
        else:
            return self.current_highest_bid.amount
    
    @property
    def current_highest_bid(self):
        return self.bids.order_by("-amount").first()

    # If auction time ends save the highest bid user as winner
    def determine_winner(self):
        if not self.is_active:
            highest_bid = self.current_highest_bid
            if highest_bid:
                self.winner = highest_bid.user
                self.save()

    # I can call this function manually after ending the auction to determine the winner 
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        #  Checking that the auction finished and there is no existing winner already
        if not self.winner and not self.is_active:
            self.determine_winner()


# User bids on auctions
class Bid(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name='bids')
    auction = models.ForeignKey("AuctionListing", on_delete=models.CASCADE, related_name='bids')
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Bid by {self.user.username} on {self.auction.title}"


# User / Auction Comment
class Comment(models.Model):
    commented_by = models.ForeignKey("User", on_delete=models.CASCADE, related_name='comments')
    auction = models.ForeignKey("AuctionListing", on_delete=models.CASCADE, related_name='comments')
    datetime_commented = models.DateTimeField(auto_now_add=True)
    comment_text = models.TextField()

    def __str__(self):
        return f"Comment by {self.commented_by.username} on {self.auction.title}"


# Auction Category
class Category(models.Model):
    name = models.CharField(max_length=250)

    def __str__(self):
        return self.name
    