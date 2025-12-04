# main.py - Entry point for pygbag web deployment
# This file is required by pygbag to run the game in a browser

import asyncio

# Import and run the game
from ur_gui import main

asyncio.run(main())

