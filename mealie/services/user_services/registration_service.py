from logging import Logger
from uuid import uuid4

from fastapi import HTTPException, status

from mealie.core.security import hash_password
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.group.group_preferences import CreateGroupPreferences
from mealie.schema.user.registration import CreateUserRegistration
from mealie.schema.user.user import GroupBase, GroupInDB, PrivateUser, UserIn
from mealie.services.group_services.group_service import GroupService


class RegistrationService:
    logger: Logger
    repos: AllRepositories

    def __init__(self, logger: Logger, db: AllRepositories):
        self.logger = logger
        self.repos = db

    def _create_new_user(self, group: GroupInDB, new_group: bool) -> PrivateUser:
        new_user = UserIn(
            email=self.registration.email,
            username=self.registration.username,
            password=hash_password(self.registration.password),
            full_name=self.registration.username,
            advanced=self.registration.advanced,
            group=group.name,
            can_invite=new_group,
            can_manage=new_group,
            can_organize=new_group,
        )

        return self.repos.users.create(new_user)

    def _register_new_group(self) -> GroupInDB:
        group_data = GroupBase(name=self.registration.group)

        group_preferences = CreateGroupPreferences(
            group_id=uuid4(),
            private_group=self.registration.private,
            first_day_of_week=0,
            recipe_public=not self.registration.private,
            recipe_show_nutrition=self.registration.advanced,
            recipe_show_assets=self.registration.advanced,
            recipe_landscape_view=False,
            recipe_disable_comments=self.registration.advanced,
            recipe_disable_amount=self.registration.advanced,
        )

        return GroupService.create_group(self.repos, group_data, group_preferences)

    def register_user(self, registration: CreateUserRegistration) -> PrivateUser:
        self.registration = registration

        self.logger.info(f"Registering user {registration.username}")
        token_entry = None
        new_group = False

        if registration.group:
            new_group = True
            group = self._register_new_group()

        elif registration.group_token and registration.group_token != "":
            token_entry = self.repos.group_invite_tokens.get_one(registration.group_token)
            if not token_entry:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "Invalid group token"})
            group = self.repos.groups.get_one(token_entry.group_id)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "Missing group"})

        user = self._create_new_user(group, new_group)

        if token_entry and user:
            token_entry.uses_left = token_entry.uses_left - 1

            if token_entry.uses_left == 0:
                self.repos.group_invite_tokens.delete(token_entry.token)

            else:
                self.repos.group_invite_tokens.update(token_entry.token, token_entry)

        return user