# Safecor Demonstration application

## How it works

This demonstration project highlights the inter-domain communication mechanisms of the Safecor platform.

The graphical interface provides an input field that allows the user to enter a message. The message is then sent through the broker and received by a first component that enriches it before emitting a response. This response is then captured by a second component that enriches it in turn.

To illustrate the flow of requests to the platform, each component enriches the initial message with elements from the system:
- nb_cpu - The number of CPUs of the system.
- is_plugged - true if the system is connected to AC power, false if it is running on battery.

### Commands and messages

The `topics` used are the following:

| Topic | Arguments | Description |
|--|--|--|
| `demo/lambda/request` | `{ "message": "the message entered by the user" }` | The message entered by the user is transmitted to the system components through this topic. |
| `demo/lambda/step/#` | `{ "message": "the message entered by the user and enriched at step #" }` | The message is processed by one of the components, enriched, and then transmitted. |
| `demo/lambda/response` | `{ "result": "the final enriched message" }` | The result of the processing is returned through this message. |

### Components

The demonstration system has 3 components:

| Component | Role | File |
|--|--|--|
| GUI | Displays the graphical interface and handles the interactions with the user | `AppController.py` |
| Component 1 | First enrichment component | `Composant1.py` |
| Component 2 | Second enrichment component | `Composant2.py` |

## Dependencies

Building the wheel package requires the python `build` module:
```
$ pip install build
```

**An Internet connection is required**

## Build

```
$ python3 -m build --no-isolation
```
