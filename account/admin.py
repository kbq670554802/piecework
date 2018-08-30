from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import Group, Permission
from django.forms import ModelMultipleChoiceField

import xadmin
from account.models import MyGroup, MyUser, MyPermission, WorkType, WageType, AttendanceShift, Position, DepartureType
from xadmin.plugins.auth import GroupAdmin, UserAdmin, PermissionAdmin, ACTION_NAME
from xadmin.views import filter_hook

from xadmin.layout import Fieldset, Main, Side, Row, FormHelper


def get_permission_name(p):
    action = p.codename.split('_')[0]
    if action in ACTION_NAME:
        return ACTION_NAME[action] % str(p.content_type)
    else:
        return p.name


class PermissionModelMultipleChoiceField(ModelMultipleChoiceField):

    def label_from_instance(self, p):
        return get_permission_name(p)


class GroupModelMultipleChoiceField(ModelMultipleChoiceField):

    def label_from_instance(self, p):
        # return get_permission_name(p)
        return p.name


class MyUserAdmin(object):
    change_user_password_template = None
    list_display = (
        'username', 'name', 'card_number', 'card_number_attendance', 'groups', 'position', 'gender', 'wage_type',
        'attendance_shift', 'attendance_shift', 'attendance_shift', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'gender', 'departure_ype', 'wage_type', 'groups',)
    search_fields = ('username', 'email', 'name')
    ordering = ('username',)
    style_fields = {
        'user_permissions': 'm2m_transfer',
        'groups': 'm2m_transfer',
    }
    model_icon = 'fa fa-user'
    relfield_style = 'fk-ajax'
    readonly_fields = ('operator_time', 'operator_last_time', 'last_login', 'operator', 'operator_last',)
    EMPTY_CHANGELIST_VALUE = ''

    def get_field_attrs(self, db_field, **kwargs):
        attrs = super(MyUserAdmin, self).get_field_attrs(db_field, **kwargs)
        if db_field.name == 'user_permissions':
            attrs['form_class'] = PermissionModelMultipleChoiceField

        if db_field.name == 'groups':
            attrs['form_class'] = GroupModelMultipleChoiceField
        return attrs

    def get_model_form(self, **kwargs):
        if self.org_obj is None:
            self.form = UserCreationForm
        else:
            self.form = UserChangeForm
        return super(MyUserAdmin, self).get_model_form(**kwargs)

    def get_form_layout(self):
        if self.org_obj:
            self.form_layout = (
                Main(
                    Fieldset('',
                             'username', 'password',
                             css_class='unsort no_title'
                             ),
                    Fieldset('个人信息',
                             Row(),
                             'name',
                             'mobile',
                             'email',
                             'card_number',
                             'card_number_attendance',
                             'wage_type',
                             'work_type',
                             'attendance_shift',
                             'position',
                             'attendance_shift',
                             ),
                    Fieldset('权限',
                             'groups', 'user_permissions'
                             ),
                    Fieldset('重要日期',
                             'operator',
                             'operator_time',
                             'operator_last',
                             'operator_last_time',
                             'date_joined_company',
                             'last_login',
                             ),
                ),
                Side(
                    Fieldset('状态',
                             'is_active', 'is_staff', 'is_superuser',
                             ),
                )
            )
        return super(MyUserAdmin, self).get_form_layout()

    def save_models(self):
        """
        保存数据到数据库中
        """
        obj = self.new_obj
        if obj.id is None or obj.id <= 0:
            obj.operator = self.user
        obj.operator_last = self.user

        obj.save()


class MyGroupAdmin(GroupAdmin):
    model_icon = 'fa fa-cog'


class MyPermissionAdmin(PermissionAdmin):
    model_icon = 'fa fa-cog'


xadmin.site.unregister(Group)
xadmin.site.unregister(MyUser)
xadmin.site.unregister(Permission)

xadmin.site.register(MyUser, MyUserAdmin)
xadmin.site.register(MyGroup, MyGroupAdmin)
xadmin.site.register(MyPermission, MyPermissionAdmin)
xadmin.site.register(WorkType)
xadmin.site.register(WageType)
xadmin.site.register(AttendanceShift)
xadmin.site.register(Position)
xadmin.site.register(DepartureType)

# class MyUserAdmin(admin.ModelAdmin):
#     pass
#
#
# admin.site.register(User)
