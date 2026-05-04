from django.db import models

# Create your models here.
class CSVFile(models.Model):
    file = models.FileField(upload_to='csv_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name