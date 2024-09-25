#!/bin/bash

# Add Microsoft repository key and package
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list

# Update package lists
apt-get update

# Install the msodbcsql17 driver
ACCEPT_EULA=Y apt-get install -y msodbcsql17
