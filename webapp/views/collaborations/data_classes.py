from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from flask import url_for
from flask_login import current_user

from webapp.pages import *
import webapp.views.collaborations.collaborations as collaborations


@dataclass()
class CollaborationRecord2:
    collaboration_case: Enum
    lock_status: Enum
    actions: list
    collab_id: int
    package_id: int
    package_name: str
    owner_id: int
    owner_login: str
    owner_name: str
    collaborator_id: int
    collaborator_login: str
    collaborator_name: str
    locked_by_id: int
    locked_by: str
    status_str: str
    action_str: str

    def update_action_str(self, action_str):
        if len(self.action_str) > 0:
            self.action_str += '<br>'
        self.action_str += action_str

    def __post_init__(self):
        current_user_login = current_user.get_user_org()
        current_user_id = collaborations.get_user(current_user_login).user_id
        self.owner_name = collaborations.display_name(self.owner_login)
        self.collaborator_name = collaborations.display_name(self.collaborator_login)

        is_group_entry = self.collaborator_login.endswith('-group_collaboration')
        # if is_group_entry:
        #     self.locked_by = self.collaborator_login
        # else:
        if self.locked_by_id is not None:
            self.locked_by = collaborations._get_user(self.locked_by_id).user_login

        # Status
        if self.lock_status == collaborations.LockStatus.NOT_LOCKED:
            self.status_str = 'Available'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_LOGGED_IN_USER:
            if not is_group_entry:
                self.status_str = 'Locked by ' + collaborations.display_name(self.locked_by)
            else:
                # The group lock is available
                self.status_str = 'Available'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_ANOTHER_USER:
            self.status_str = 'Locked by ' + collaborations.display_name(self.locked_by)

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_GROUP_ONLY:
            if self.collaboration_case == collaborations.CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR and\
                   is_group_entry:
                self.status_str = f'Locked by {self.collaborator_name}'
            else:
                self.status_str = 'Available'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER:
            if not is_group_entry:
                self.status_str = 'Locked by ' + collaborations.display_name(self.locked_by)
            else:
                self.status_str = 'Locked by ' + collaborations.display_name(self.collaborator_login)

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_GROUP_AND_ANOTHER_USER:
            self.status_str = 'Locked by ' + collaborations.display_name(self.locked_by)

        # Actions
        for action in self.actions:
            if action == collaborations.CollaborationAction.OPEN:
                if self.collaboration_case == collaborations.CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR:
                    link = url_for(PAGE_OPEN_BY_COLLABORATOR, collaborator_id=self.collaborator_id,
                                   package_id=self.package_id)
                    self.update_action_str(f'<a href="{link}">Open</a>')

            if action == collaborations.CollaborationAction.RELEASE_INDIVIDUAL_LOCK:
                # if self.collaborator_id == current_user_id:
                link = url_for(PAGE_RELEASE_LOCK, package_id=self.package_id)
                self.update_action_str(f'<a href="{link}">Release lock</a>')

            if action == collaborations.CollaborationAction.RELEASE_GROUP_LOCK:
                link = url_for(PAGE_RELEASE_GROUP_LOCK, package_id=self.package_id)
                self.update_action_str(f'<a href="{link}">Release group lock</a>')

            if action == collaborations.CollaborationAction.APPLY_GROUP_LOCK:
                link = url_for(PAGE_APPLY_GROUP_LOCK,
                               package_id=self.package_id,
                               group_id=self.collaborator_id)
                self.update_action_str(f'<a href="{link}">Apply group lock</a>')

            if action == collaborations.CollaborationAction.END_COLLABORATION:
                link = url_for(PAGE_REMOVE_COLLABORATION, collab_id=self.collab_id)
                onclick = f"return confirm('Are you sure? This will end the collaboration for all participants and " \
                          f"cannot be undone.');"
                self.update_action_str(f'<a href="{link}" onclick="{onclick}">End collaboration</a>')

            if action == collaborations.CollaborationAction.END_GROUP_COLLABORATION:
                link = url_for(PAGE_REMOVE_COLLABORATION, collab_id=self.collab_id)
                onclick = f"return confirm('Are you sure? This will end the collaboration for all participants and " \
                                  f"cannot be undone.');"
                self.update_action_str(f'<a href="{link}" onclick="{onclick}">End group collaboration</a>')

    def __lt__(self, other):
        if self.package_name < other.package_name:
            return True
        elif self.package_name == other.package_name:
            if self.owner_name.lower() < other.owner_name.lower():
                return True
            elif self.owner_name.lower() == other.owner_name.lower():
                if self.collaborator_name.lower() < other.collaborator_name.lower():
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False


"""
CollaborationRecord is a dataclass that is used to represent a collaboration in a displayable form.
"""
@dataclass()
class CollaborationRecord:
    collaboration_case: Enum
    # lock_status: Enum
    collab_id: int
    package_id: int
    package: str
    owner_id: int
    owner_login: str
    owner_name: str
    collaborator_is_group: bool
    collaborator_id: int
    collaborator_login: str
    collaborator_name: str
    status: str
    locked_by_id: int
    locked_by: str
    action: str

    def __post_init__(self):
        current_user_login = current_user.get_user_org()
        current_user_id = collaborations.get_user(current_user_login).user_id
        self.owner_name = collaborations.display_name(self.owner_login)
        self.collaborator_name = collaborations.display_name(self.collaborator_login)

        # collaboration_case = self._calculate_case(current_user_id)

        # Handle locks
        if not self.locked_by_id:
            # Not locked by anyone
            lock_status = 'LockStatus.AVAILABLE'
            self.status = 'Available'
            if self.collaborator_login == current_user_login:
                # If there is a group lock on the package, only a group member can open the package.
                group_lock = collaborations._get_group_lock(self.package_id)
                if group_lock:
                    if collaborations.is_group_member(current_user_login, group_lock.locked_by):
                        link = url_for(PAGE_OPEN_BY_COLLABORATOR, collaborator_id=self.collaborator_id,
                                       package_id=self.package_id)
                        self.action = f'<a href="{link}">Open</a>'
                else:
                    link = url_for(PAGE_OPEN_BY_COLLABORATOR, collaborator_id=self.collaborator_id,
                                   package_id=self.package_id)
                    self.action = f'<a href="{link}">Open</a>'

            # Not locked by group but user is a member of the group, so user can apply a group lock,
            #  unless there is already a user lock by someone outside the group.
            if self.collaborator_is_group and \
                    collaborations.is_group_member(current_user_login, self.collaborator_id):
                locking_user = None
                lock = collaborations._get_lock(self.package_id)
                if lock:
                    locking_user = collaborations._get_user(lock.locked_by)
                if (not locking_user and collaborations.is_group_member(current_user_login, self.collaborator_id)) or\
                        (locking_user and collaborations.is_group_member(locking_user.user_login, lock.locked_by)):
                    link = url_for(PAGE_APPLY_GROUP_LOCK,
                                   package_id=self.package_id,
                                   group_id=self.collaborator_id)
                    self.action = f'<a href="{link}">Apply group lock</a>'

        else:
            # Locked. Might be a user or a group.
            self.locked_by = collaborations._get_user(self.locked_by_id).user_login
            self.status = 'Locked by ' + collaborations.display_name(self.locked_by)
            if self.locked_by.endswith('-group_collaboration'):
                lock_status = 'LockStatus.LOCKED_BY_GROUP'
                # There is a group lock. If the user is a member of the group, the user can release the lock.
                if collaborations.is_group_member(current_user_login, self.collaborator_id):
                    link = url_for(PAGE_RELEASE_GROUP_LOCK, package_id=self.package_id)
                    self.action = f'<a href="{link}">Release group lock</a>'
            else:
                # Individual lock. If the user is the lock holder, the user can release the lock.
                lock_status = 'LockStatus.LOCKED_BY_USER'
                if self.locked_by_id == current_user_id: # blah self.collaborator_id:
                    link = url_for(PAGE_RELEASE_LOCK, package_id=self.package_id)
                    self.action = f'<a href="{link}">Release lock</a>'

        # Handle links for ending a collaboration.
        if lock_status == 'LockStatus.LOCKED_BY_USER':
            # Only the owner can end a collaboration, and only if the owner currently has the lock.
            if current_user_login == self.owner_login and self.locked_by == current_user_login:
                link = url_for(PAGE_REMOVE_COLLABORATION, collab_id=self.collab_id)
                if len(self.action) > 0:
                    self.action += '<br>'
                onclick = f"return confirm('Are you sure? This will end the collaboration for all participants and " \
                          f"cannot be undone.');"
                self.action += f'<a href="{link}" onclick="{onclick}">End collaboration</a>'

        elif lock_status == 'LockStatus.LOCKED_BY_GROUP':
            # Only a group member can end a collaboration, and only if the group member has a user lock.
            if collaborations.is_group_member(current_user_login, self.collaborator_id):
                lock = collaborations._get_lock(self.package_id)
                if lock and lock.locked_by == current_user_id:
                    link = url_for(PAGE_REMOVE_COLLABORATION, collab_id=self.collab_id)
                    if len(self.action) > 0:
                        self.action += '<br>'
                    onclick = f"return confirm('Are you sure? This will end the collaboration for all participants and " \
                              f"cannot be undone.');"
                    self.action += f'<a href="{link}" onclick="{onclick}">End group collaboration</a>'


    def __lt__(self, other):
        if self.package < other.package:
            return True
        elif self.package == other.package:
            if self.owner_name.lower() < other.owner_name.lower():
                return True
            elif self.owner_name.lower() == other.owner_name.lower():
                if self.collaborator_name.lower() < other.collaborator_name.lower():
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False


"""
InvitationRecord is a dataclass that is used to represent an invitation in a displayable form.
"""
@dataclass()
class InvitationRecord:
    invitation_id: int
    package_id: int
    package: str
    invitee_name: str
    invitee_email: str
    date: str
    action: str

    def __post_init__(self):
        current_user_login = current_user.get_user_org()
        if current_user_login == collaborations.get_package_owner(self.package_id).user_login:
            link = url_for(PAGE_CANCEL_INVITATION, invitation_id=self.invitation_id)
            self.action = f'<a href="{link}">Cancel invitation</a>'

    def __lt__(self, other):
        if self.package.lower() < other.package.lower():
            return True
        elif self.package.lower() == other.package.lower():
            if self.invitee_name.lower() < other.invitee_name.lower():
                return True
            elif self.invitee_name.lower() == other.invitee_name.lower():
                if self.date < other.date:
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False


@dataclass()
class CollaborationOutput:
    collab_id: int
    owner_id: int
    collaborator_id: int
    package_id: int


@dataclass()
class UserOutput:
    user_id: int
    user_login: str
    active_package_id: int


@dataclass()
class PackageOutput:
    package_id: int
    owner_login: str
    package_name: str


@dataclass()
class LockOutput:
    owner: str
    package_name: str
    locked_by: str
    timestamp: datetime
