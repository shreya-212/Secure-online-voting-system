from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.


class User(AbstractUser):
    ROLE_CHOICE=(
        ('voter','Voter'),
        ('admin','Admin'),
    )
    role=models.CharField(max_length=10,choices=ROLE_CHOICE,default='voter',null=False,blank=False)
    mobile_number=models.CharField(max_length=12,null=True,blank=False)