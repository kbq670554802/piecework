from django.contrib import auth
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import models
from django.db.models.manager import EmptyManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def update_last_login(sender, user, **kwargs):
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])


class MyPermissionManager(models.Manager):
    use_in_migrations = True

    def get_by_natural_key(self, codename, app_label, model):
        return self.get(
            codename=codename,
            content_type=ContentType.objects.db_manager(self.db).get_by_natural_key(app_label, model),
        )


class MyPermission(models.Model):
    """
    The permissions system provides a way to assign permissions to specific
    users and groups of users.

    The permission system is used by the Django admin site, but may also be
    useful in your own code. The Django admin site uses permissions as follows:

        - The "add" permission limits the user's ability to view the "add" form
          and add an object.
        - The "change" permission limits a user's ability to view the change
          list, view the "change" form and change an object.
        - The "delete" permission limits the ability to delete an object.

    Permissions are set globally per type of object, not per specific object
    instance. It is possible to say "Mary may change news stories," but it's
    not currently possible to say "Mary may change news stories, but only the
    ones she created herself" or "Mary may only change news stories that have a
    certain status or publication date."

    Three basic permissions -- add, change and delete -- are automatically
    created for each Django model.
    """
    name = models.CharField(_('name'), max_length=255)
    content_type = models.ForeignKey(
        ContentType,
        models.CASCADE,
        verbose_name=_('content type'),
    )
    codename = models.CharField(_('codename'), max_length=100)
    objects = MyPermissionManager()

    class Meta:
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')
        unique_together = (('content_type', 'codename'),)
        ordering = ('content_type__app_label', 'content_type__model',
                    'codename')

    def __str__(self):
        return "%s | %s | %s" % (
            self.content_type.app_label,
            self.content_type,
            self.name,
        )

    def natural_key(self):
        return (self.codename,) + self.content_type.natural_key()

    natural_key.dependencies = ['contenttypes.contenttype']


class MyGroupManager(models.Manager):
    use_in_migrations = True

    def get_by_natural_key(self, name):
        return self.get(name=name)


class MyGroup(models.Model):
    name = models.CharField(_('name'), max_length=80, unique=True)
    # code = models.CharField('代码', max_length=80, unique=True, default='')
    permissions = models.ManyToManyField(
        MyPermission,
        verbose_name=_('permissions'),
        blank=True,
        related_name="mygroup_set",
        related_query_name="mygroup",
    )

    objects = MyGroupManager()

    class Meta:
        verbose_name = '部门'
        verbose_name_plural = '部门'

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        """
        Create and save a user with the given username, email, and password.
        """
        if not username:
            raise ValueError('The given username must be set')
        email = self.normalize_email(email)
        username = self.model.normalize_username(username)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(username, email, password, **extra_fields)


# A few helper functions for common logic between User and AnonymousUser.
def _user_get_all_permissions(user, obj):
    permissions = set()
    for backend in auth.get_backends():
        if hasattr(backend, "get_all_permissions"):
            permissions.update(backend.get_all_permissions(user, obj))
    return permissions


def _user_has_perm(user, perm, obj):
    """
    A backend can raise `PermissionDenied` to short-circuit permission checking.
    """
    for backend in auth.get_backends():
        if not hasattr(backend, 'has_perm'):
            continue
        try:
            if backend.has_perm(user, perm, obj):
                return True
        except PermissionDenied:
            return False
    return False


def _user_has_module_perms(user, app_label):
    """
    A backend can raise `PermissionDenied` to short-circuit permission checking.
    """
    for backend in auth.get_backends():
        if not hasattr(backend, 'has_module_perms'):
            continue
        try:
            if backend.has_module_perms(user, app_label):
                return True
        except PermissionDenied:
            return False
    return False


class MyPermissionsMixin(models.Model):
    """
    Add the fields and methods necessary to support the Group and Permission
    models using the ModelBackend.
    """
    is_superuser = models.BooleanField(
        _('superuser status'),
        default=False,
        help_text=_(
            'Designates that this user has all permissions without '
            'explicitly assigning them.'
        ),
    )
    groups = models.ManyToManyField(
        MyGroup,
        verbose_name='部门',
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name="myuser_set",
        related_query_name="myuser",
    )
    user_permissions = models.ManyToManyField(
        MyPermission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name="myuser_set",
        related_query_name="myuser",
    )

    class Meta:
        abstract = True

    def get_group_permissions(self, obj=None):
        """
        Return a list of permission strings that this user has through their
        groups. Query all available auth backends. If an object is passed in,
        return only permissions matching this object.
        """
        permissions = set()
        for backend in auth.get_backends():
            if hasattr(backend, "get_group_permissions"):
                permissions.update(backend.get_group_permissions(self, obj))
        return permissions

    def get_all_permissions(self, obj=None):
        return _user_get_all_permissions(self, obj)

    def has_perm(self, perm, obj=None):
        """
        Return True if the user has the specified permission. Query all
        available auth backends, but return immediately if any backend returns
        True. Thus, a user who has permission from a single auth backend is
        assumed to have permission in general. If an object is provided, check
        permissions for that object.
        """
        # Active superusers have all permissions.
        if self.is_active and self.is_superuser:
            return True

        # Otherwise we need to check the backends.
        return _user_has_perm(self, perm, obj)

    def has_perms(self, perm_list, obj=None):
        """
        Return True if the user has each of the specified permissions. If
        object is passed, check if the user has all required perms for it.
        """
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, app_label):
        """
        Return True if the user has any permissions in the given app label.
        Use simlar logic as has_perm(), above.
        """
        # Active superusers have all permissions.
        if self.is_active and self.is_superuser:
            return True

        return _user_has_module_perms(self, app_label)


class WorkType(models.Model):
    """
       用工形式，合同工或者临时工
    """
    name = models.CharField("名称", max_length=80, unique=True)

    class Meta:
        verbose_name = '用工形式'
        verbose_name_plural = '用工形式'

    def __str__(self):
        return self.name


class WageType(models.Model):
    """
       用工类型， 工资的计算方式
    """
    name = models.CharField("名称", max_length=80, unique=True)

    class Meta:
        verbose_name = '用工类型'
        verbose_name_plural = '用工类型'

    def __str__(self):
        return self.name


class AttendanceShift(models.Model):
    """
       考勤班次
    """
    name = models.CharField("名称", max_length=80, unique=True)

    class Meta:
        verbose_name = '考勤班次'
        verbose_name_plural = '考勤班次'

    def __str__(self):
        return self.name


class Position(models.Model):
    """
       职务
    """
    name = models.CharField("名称", max_length=80, unique=True)

    class Meta:
        verbose_name = '职务'
        verbose_name_plural = '职务'

    def __str__(self):
        return self.name


class DepartureType(models.Model):
    """
       离职类型
    """
    name = models.CharField("名称", max_length=80, unique=True)

    class Meta:
        verbose_name = '离职类型'
        verbose_name_plural = '离职类型'

    def __str__(self):
        return self.name


class MyAbstractUser(AbstractBaseUser, MyPermissionsMixin):
    GENDER_CHOICES = (
        ('M', '男'),
        ('F', '女'),
    )

    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[username_validator],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )

    card_number = models.CharField('员工卡号', max_length=30, blank=True, null=True, default='', )
    card_number_attendance = models.CharField('考勤卡号', max_length=30, blank=True, null=True, default='', )
    name = models.CharField('姓名', max_length=100, blank=True, null=True, )
    idcard = models.CharField('身份证号', max_length=20, blank=True, null=True, )
    bank_card = models.CharField('银行卡号', max_length=30, blank=True, null=True, )
    mobile = models.CharField('手机号', max_length=20, blank=True, null=True, )
    email = models.EmailField('邮箱', blank=True, null=True, )
    birth = models.DateField('出生日期', blank=True, null=True)
    gender = models.CharField('性别', max_length=2, choices=GENDER_CHOICES, null=True, blank=True)
    remark = models.TextField('备注', max_length=500, blank=True, null=True, )
    wage_type = models.ForeignKey(
        WageType,
        models.SET_NULL,
        verbose_name='用工类型',
        blank=True,
        null=True,
    )
    work_type = models.ForeignKey(
        WorkType,
        models.SET_NULL,
        verbose_name='用工形式',
        blank=True,
        null=True,
    )
    attendance_shift = models.ForeignKey(
        AttendanceShift,
        models.SET_NULL,
        verbose_name='考勤班次',
        blank=True,
        null=True,
    )
    position = models.ForeignKey(
        Position,
        models.SET_NULL,
        verbose_name='职务',
        blank=True,
        null=True,
    )
    departure_ype = models.ForeignKey(
        DepartureType,
        models.SET_NULL,
        verbose_name='离职类型',
        blank=True,
        null=True,
    )
    operator = models.ForeignKey(
        'self',
        models.SET_NULL,
        verbose_name='操作者',
        null=True,
        blank=True,
        related_name="myuser_operator",
    )
    operator_last = models.ForeignKey(
        'self',
        models.SET_NULL,
        verbose_name='最后操作者',
        null=True,
        blank=True,
        # related_name="operator_last",
    )
    date_joined_company = models.DateField('进厂时间', default=timezone.now, null=True, blank=True)
    operator_time = models.DateTimeField('操作时间', auto_now_add=True, null=True, blank=True)
    operator_last_time = models.DateTimeField('最后操作时间', auto_now=True, null=True, blank=True)
    last_login = models.DateTimeField('最后登录', null=True, blank=True)

    is_staff = models.BooleanField(
        '职员状态',
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
        '有效',
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )

    objects = UserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        abstract = True

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        """Return the short name for the user."""
        return self.name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def __str__(self):
        return '%s' % self.name


class MyUser(MyAbstractUser):
    """
    Users within the Django authentication system are represented by this
    model.

    Username and password are required. Other fields are optional.
    """

    class Meta(MyAbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'


class MyAnonymousUser:
    id = None
    pk = None
    username = ''
    is_staff = False
    is_active = False
    is_superuser = False
    _groups = EmptyManager(MyGroup)
    _user_permissions = EmptyManager(MyPermission)

    def __str__(self):
        return 'MyAnonymousUser'

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __hash__(self):
        return 1  # instances always return the same hash value

    def save(self):
        raise NotImplementedError("Django doesn't provide a DB representation for MyAnonymousUser.")

    def delete(self):
        raise NotImplementedError("Django doesn't provide a DB representation for MyAnonymousUser.")

    def set_password(self, raw_password):
        raise NotImplementedError("Django doesn't provide a DB representation for MyAnonymousUser.")

    def check_password(self, raw_password):
        raise NotImplementedError("Django doesn't provide a DB representation for MyAnonymousUser.")

    @property
    def groups(self):
        return self._groups

    @property
    def user_permissions(self):
        return self._user_permissions

    def get_group_permissions(self, obj=None):
        return set()

    def get_all_permissions(self, obj=None):
        return _user_get_all_permissions(self, obj=obj)

    def has_perm(self, perm, obj=None):
        return _user_has_perm(self, perm, obj=obj)

    def has_perms(self, perm_list, obj=None):
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, module):
        return _user_has_module_perms(self, module)

    @property
    def is_anonymous(self):
        return True

    @property
    def is_authenticated(self):
        return False

    def get_username(self):
        return self.username
