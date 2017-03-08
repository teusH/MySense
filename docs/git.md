# GIT the stupid content tracker
Git gives you the help to install and maintain a software package distribution say e.g. from https://github.com

The software will be located in the directory where you initiate the git command. See gittutorial (manual section 7) to get started.

MySense will use git to download dependent Python based packages e.g. from Adafruit and Grove.

## intro
To download a package run the command `git clone https://github.com/path.../package`
This will create the directory `package` into your current directory. Go into that directory `cd package` and to install the libray for a Python package run `python setup.py install`. BUT look into the `REDAME.md` file first!

To update the package: change directory to the *package* directory:
```shell
    cd package
    git fetch -- all               # update all what is in here
    git reset --hard origin/master # update and overwrite ALL from the master
```
Note that the update will overwrite all your changes (except those which are not known to git) on the distribution files you made for local purpose in the past!

## contribute
Contribute to the distributions the software and desciptions you improved!
