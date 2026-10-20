from django.test import TestCase
from .models import ProductReview


class PublicNameTests(TestCase):
    def test_email_is_hidden(self):
        review = ProductReview(reviewer_name='someone@example.com', reviewer_email='someone@example.com')
        self.assertEqual(review.public_name, 'Verified customer')

    def test_plain_name_is_kept(self):
        review = ProductReview(reviewer_name='Jane Doe', reviewer_email='jane@example.com')
        self.assertEqual(review.public_name, 'Jane Doe')
