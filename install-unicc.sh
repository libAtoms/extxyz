#!/bin/sh

git clone https://github.com/phorward/unicc.git
cd unicc
git checkout develop
./configure --prefix=/usr/local
make
sudo make install
