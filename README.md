# Python Analysis Plugin for feather-city

This is a plugin for the [feather-city](https://test.pypi.org/project/feather-city/) project, developed by me, as a basic analyser for Python projects. The plugin works by installing it together with the main feather-city library in the same virtual environment, then using it in as an analyser by specifying the "python" language.

## Features
- computes the lines of code, lines of comments, number of methods and total lines for each python file of a project

## Installing
- to run the plugin, you need the main [feather-city](https://test.pypi.org/project/feather-city/) library installed on the same virtual environment as the python plugin. You can install feather, download the python plugin and install it in the same environment using `pip install .` when the working directory is the same as the directory where you downloaded the python plugin
## More Details

- [feather-city](https://test.pypi.org/project/feather-city/) is a project developed by me for my Master's thesis and is an lightweight and extensible library for writing analysers and visualisers for static code analysis metrics, using a data interface designed by me (very similar to SARIF and on the way to match it)
- You can use this plugin in the [feather-city](https://github.com/livcristi/feather-city-action) GitHub action
