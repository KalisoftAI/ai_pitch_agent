from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """
    Authenticate with either the username or the email address.

    The sign-in form advertises "Username or Email", and signup collects a
    unique email, so users reasonably expect either to work. This backend
    keeps the standard ModelBackend permission behaviour while resolving an
    email to its matching account.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()

        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        username = username.strip()
        try:
            user = UserModel.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except UserModel.DoesNotExist:
            # Run the default hasher once to mitigate timing attacks against
            # user enumeration (same trick as ModelBackend).
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            # Duplicate emails are possible in legacy data; prefer an exact
            # username match, otherwise the oldest account with that email.
            user = (
                UserModel.objects.filter(username__iexact=username).first()
                or UserModel.objects.filter(email__iexact=username).order_by('id').first()
            )

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
