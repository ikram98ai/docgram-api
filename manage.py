import typer
from app.models import (
    UserModel,
    PostModel,
    LikeModel,
    CommentModel,
    FollowModel,
    ChatConversationModel,
    ChatMessageModel,
    Notification,
)
from app.utils import hash, is_strong_password

app = typer.Typer()


@app.command()
def create_tables():
    """
    Create database tables.
    """
    tables = [
        UserModel,
        PostModel,
        LikeModel,
        CommentModel,
        FollowModel,
        ChatConversationModel,
        ChatMessageModel,
        Notification,
    ]
    for table in tables:
        if not table.exists():
            print(f"Creating table {table.Meta.table_name}")
            table.create_table(wait=True)  # wait=True waits for table creation
        else:
            print(f"Table {table.Meta.table_name} already exists")


@app.command()
def create_admin(
    username: str = typer.Option(..., "--username", "-u"),
    email: str = typer.Option(..., "--email", "-e"),
):
    """
    Create a new admin user.
    """
    password = typer.prompt("Enter password", hide_input=True)
    password_confirm = typer.prompt("Confirm password", hide_input=True)

    if password != password_confirm:
        print("Passwords do not match.")
        raise typer.Exit()

    if not is_strong_password(password):
        print(
            "Password is not strong enough. It must be at least 8 characters long and contain at least one uppercase and one lowercase letter."
        )
        raise typer.Exit()

    hashed_password = hash(password)
    admin_user = UserModel(
        username=username,
        email=email,
        password=hashed_password,
        is_superuser=True,
    )
    admin_user.save()
    print(f"Admin user '{username}' created successfully.")


@app.command()
def list_admins():
    """
    List all admin users.
    """
    confirmation = input(
        "Are you sure you want to list all admin users? Enter yes continue: "
    )
    if confirmation.lower() != "yes":
        print("Operation cancelled.")
        raise typer.Exit()
    admins = UserModel.scan(UserModel.is_superuser == True)
    for admin in admins:
        print(f"ID: {admin.id}, Username: {admin.username}, Email: {admin.email}")


@app.command()
def update_admin(
    user_id: str = typer.Option(..., "--id"),
    username: str = typer.Option(None, "--username", "-u"),
    email: str = typer.Option(None, "--email", "-e"),
):
    """
    Update an admin user's details.
    """
    try:
        admin = UserModel.get(user_id)
        if admin.is_superuser == False:
            print(f"User with ID {user_id} is not an admin.")
            raise typer.Exit()

        if username:
            admin.update(actions=[UserModel.username.set(username)])
        if email:
            admin.update(actions=[UserModel.email.set(email)])

        print(f"Admin with ID {user_id} updated successfully.")
    except UserModel.DoesNotExist:
        print(f"Admin with ID {user_id} not found.")
        raise typer.Exit()


@app.command()
def delete_admin(user_id: str = typer.Option(..., "--id")):
    """
    Delete an admin user.
    """
    try:
        admin = UserModel.get(user_id)
        if admin.is_superuser == False:
            print(f"User with ID {user_id} is not an admin.")
            raise typer.Exit()

        admin.delete()
        print(f"Admin with ID {user_id} deleted successfully.")
    except UserModel.DoesNotExist:
        print(f"Admin with ID {user_id} not found.")
        raise typer.Exit()


if __name__ == "__main__":
    app()
