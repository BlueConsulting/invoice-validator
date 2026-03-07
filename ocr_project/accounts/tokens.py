from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import int_to_base36
import hashlib


class CustomTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        """
        Hash the user's primary key and some user state that's sure to change
        after a password reset to produce a token that invalidates when it's used.
        """
        # Use email instead of pk for consistency
        return str(user.email) + str(timestamp)


custom_token_generator = CustomTokenGenerator()

