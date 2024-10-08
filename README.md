# View

## Introduction
This project provides a graphical user interface (GUI) designed to interact with various lightsheet instruments and define 
tiles for the acquisition processes. View was developed to work with [Voxel](https://github.com/AllenNeuralDynamics/voxel) but can work 
with other instrument and acquisition engines that follow similar structures and naming conventions. 

As view was written to be compatible with as many different types of scopes as possible, the design is modular. 
View is composed of two main windows: instrument and acquisition. The Instrument window contains all the widgets for 
devices found in the input instrument (lasers, cameras, DAQs, stages, ect.). Widgets for each device can be specified in 
the config.yaml or use the default BaseDeviceWidget if not specified. The Acquisition window contains widgets for all operations 
found in the input acquisition (data writers, data transfers, routines, ect.). Similarly to the instrument window, 
widgets each operation can be specified in the config.yaml or use the default BaseDeviceWidget if not specified. The 
Acquisition window additionally house widgets to define the scan volume for the acquisition engine. 

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Dependencies](#dependencies)
- [Configuration](#configuration)
- [Documentation](#documentation)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Contributors](#contributors)
- [License](#license)

## Features
- **Instrument Management**: Provides an interface for interacting with various instruments using the `InstrumentView` class.
- **Acquisition Management**: Handles acquisition-related tasks such as metadata management, volume planning, channel setup, and operation configuration.
- **Dynamic Device Widgets**: The `BaseDeviceWidget` dynamically generates UI elements based on the properties of the device, 
allowing flexible input fields and easy creation of custom widgets.
- **Napari Viewer**: Leverages `napari` for data visualisation before and during acquisition
- **Custom Widgets**: Includes wide array of custom device widgets to use as well as examples on how to utilize them.

## Installation

### Prerequisites
Make sure you have the following installed:
- Python 3.8 or higher
- `QtPy` (for PyQt/PySide bindings)
- `Pillow` (for image processing)
- `Napari` (for threading and possibly visualization)
- `ruamel.yaml` (for YAML configuration)
- `numpy` (for numerical computations)

You can install the required dependencies using pip:
```bash
pip install qtpy napari pillow ruamel.yaml numpy
