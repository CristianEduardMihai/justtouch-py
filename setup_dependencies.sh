#!/bin/bash

# JustTouch Kivy Android Build Dependencies Setup Script
# This script installs all necessary dependencies to build the Android APK
# Tested on Ubuntu 24.04

set -e  # exit on any error

echo "Setting up dependencies for JustTouch Kivy Android build..."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons."
   exit 1
fi

print_status "Updating package list..."
sudo apt update

print_status "Installing essential build tools..."
sudo apt install -y \
    build-essential \
    git \
    wget \
    curl \
    unzip \
    zip \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release

print_status "Installing Python development environment..."
sudo apt install -y \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    python3-setuptools \
    python3-wheel \
    libpython3-dev

print_status "Installing OpenJDK 17..."
sudo apt install -y openjdk-17-jdk openjdk-17-jre

print_status "Configuring Java 17 as default..."
sudo update-alternatives --install /usr/bin/java java /usr/lib/jvm/java-17-openjdk-amd64/bin/java 1711
sudo update-alternatives --install /usr/bin/javac javac /usr/lib/jvm/java-17-openjdk-amd64/bin/javac 1711
sudo update-alternatives --set java /usr/lib/jvm/java-17-openjdk-amd64/bin/java
sudo update-alternatives --set javac /usr/lib/jvm/java-17-openjdk-amd64/bin/javac

export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
echo "export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64" >> ~/.bashrc

print_status "Installing Android development dependencies..."
sudo apt install -y \
    libc6-dev-i386 \
    lib32z1 \
    libbz2-1.0:i386 \
    libncurses5:i386 \
    libstdc++6:i386 \
    lib32ncurses6 \
    zlib1g:i386

print_status "Installing additional libraries for Kivy..."
sudo apt install -y \
    libssl-dev \
    libffi-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev
print_status "Installing Android Debug Bridge (ADB)..."
sudo apt install -y adb

print_status "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    print_success "Created Python virtual environment"
else
    print_warning "Virtual environment already exists"
fi
print_status "Installing Python dependencies in virtual environment..."
source .venv/bin/activate

pip install --upgrade pip setuptools wheel

pip install -r requirements.txt

print_success "Python dependencies installed successfully"

print_status "Verifying Java installation..."
java_version=$(java -version 2>&1 | head -n 1)
if [[ $java_version == *"17."* ]]; then
    print_success "Java 17 is correctly installed: $java_version"
else
    print_error "Java 17 installation failed or wrong version detected"
    exit 1
fi

print_status "Verifying Python environment..."
python_version=$(python3 --version)
print_success "Python version: $python_version"

buildozer_version=$(buildozer --version 2>/dev/null || echo "Not found")
if [[ $buildozer_version != "Not found" ]]; then
    print_success "Buildozer is installed: $buildozer_version"
else
    print_error "Buildozer installation failed"
    exit 1
fi

print_status "Creating buildozer directories..."
mkdir -p ~/.buildozer

print_success "All dependencies have been successfully installed!"