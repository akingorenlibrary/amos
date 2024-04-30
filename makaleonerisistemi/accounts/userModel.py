from djongo import models

class User(models.Model):
    fullname = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    password = models.CharField(max_length=100)

    class Meta:
        abstract = True
