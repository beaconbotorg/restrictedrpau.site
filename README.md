# RestrictedRP Website + Events

This version keeps the original RestrictedRP website and adds a real `/events` page plus secure Discord role-based event management.

## Start on localhost:3000

1. Install Python 3.11+.
2. Open a terminal in this folder.
3. Run:
   `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in the Discord values.
5. In your Discord Developer Portal, add this OAuth redirect:
   `http://localhost:3000/auth/discord/callback`
6. Run:
   `python app.py`
7. Open `http://localhost:3000`.

## Multiple staff roles

Set `EVENT_MANAGER_ROLE_IDS` to every role that should be able to create/delete events. A user only needs **one** of those roles.

Example:
`EVENT_MANAGER_ROLE_IDS=111111111111111111,222222222222222222,333333333333333333`

Normal users can see Events. Only members whose Discord account has a configured event-manager role can open Manage Events or use the event API.


## Your local setup
The project is configured for `http://localhost:3000`.

1. Install Python 3.11+.
2. In this folder run:
   `pip install -r requirements.txt`
3. Start it with:
   `python app.py`
4. Open:
   `http://localhost:3000`
5. Discord OAuth must have this exact redirect URI configured:
   `http://localhost:3000/auth/discord/callback`

The supplied `.env` is already filled in for the RestrictedRP Discord server and the three event-manager roles.
