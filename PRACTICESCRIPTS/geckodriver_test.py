#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.firefox.options import Options

DRIVER = '/home/will/SHARED/UbuntuVbox/wkembelZombie/geckodriver'

options = Options()
options.add_argument("--headless")

browser = webdriver.Firefox(options=options, executable_path=DRIVER)

browser.get('https://www.google.com/')

browser.save_screenshot('LambdaTestVisibleScreen.png')
browser.quit()
