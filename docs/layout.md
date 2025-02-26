# Layout

The layout of the website is defined in `src/app/app.py` and `src/app/layout/*`. The layout is built with the [Dash](https://dash.plotly.com/) framework, which is built on top of [Flask](https://flask.palletsprojects.com/en/1.1.x/).

## app.py
The entrypoint to the app is the `app` object in `src/app/app.py`. It is a `dash.Dash` object is accessed by `main.py` via the `get_app()` function. The app is designed, so that `app.py` only contains the outermost container and the tabs accessible at the top. The actual content of each tab is defined in the respective files in `src/app/layout/`.

Additionally, the `get_app()` links the callbacks of the specific tabs to the app object. Callbacks are used to define the logic of the app, e.g., what happens when a button is clicked.

## Adding a new tab
To add a new tab, create a new file in `src/app/layout/` and define the layout of the tab in this file. Inside the file, define a function that returns the layout of the tab. Additionally, define a function to link the callbacks of the tab to the app object in `app.py`.

In `app.py`, import the new tab layout and callback function, add the layout as a new tab to the `app` object, and link the callbacks to the app object. The tab will now be accessible in the app.