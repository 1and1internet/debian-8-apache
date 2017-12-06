#!/usr/bin/env python3

import unittest
import os
import docker
from selenium import webdriver
import sys
import os.path


class Test1and1ApacheImage(unittest.TestCase):
    client = None
    container = None

    def get_share_mountpoint():
        share = os.getenv("SOURCE_MOUNT")
        if share is None or share == "":
            share = os.path.dirname(sys.argv[0])
            print("SOURCE_MOUNT is not defined, using %s" % share)
        return share

    @classmethod
    def setUpClass(cls):
        image_to_test = os.getenv("IMAGE_NAME")
        if image_to_test == "":
            raise Exception("I don't know what image to test")
        Test1and1ApacheImage.client = docker.from_env()

        share_bind = "%s/testpack/files/html" % Test1and1ApacheImage.get_share_mountpoint()
        docker_network = os.getenv("DOCKER_NETWORK", "host")

        Test1and1ApacheImage.container = Test1and1ApacheImage.client.containers.run(
            image=image_to_test,
            remove=True,
            detach=True,
            volumes={
                share_bind: {
                    'bind': '/var/www/html',
                    'mode': 'ro'
                }
            },
            network=docker_network
        )

    @classmethod
    def tearDownClass(cls):
        Test1and1ApacheImage.container.stop()

    def setUp(self):
        print ("\nIn method", self._testMethodName)
        self.container = Test1and1ApacheImage.container

    def execRun(self, command):
        return self.container.exec_run(command).decode('utf-8')

    def assertPackageIsInstalled(self, packageName):
        op = self.execRun("dpkg -l %s" % packageName)
        self.assertTrue(
            op.find(packageName) > -1,
            msg="%s package not installed" % packageName
        )

    # <tests to run>

    def test_apache2_installed(self):
        self.assertPackageIsInstalled("apache2")

    def test_apache2_running(self):
        self.assertTrue(
            self.execRun("ps -ef").find('apache2') > -1,
            msg="apache2 not running"
        )

    def test_apache2_ports(self):
        self.assertFalse(
            self.execRun("ls /etc/apache2/ports.conf").find("No such file or directory") > -1,
            msg="/etc/apache2/ports.conf is missing"
        )
        self.assertTrue(
            self.execRun("cat /etc/apache2/ports.conf").find("Listen 8080") > -1,
            msg="ports.conf misconfigured"
        )

    def test_apache2_lock(self):
        result = self.execRun("ls -ld /var/lock/apache2")
        self.assertFalse(
            result.find("No such file or directory") > -1,
            msg="/var/lock/apache2 is missing"
        )
        self.assertEqual(result[0], 'd', msg="/var/lock/apache2 is not a directory")
        self.assertEqual(result[8], 'w', msg="/var/lock/apache2 is not a writable by others")

    def test_apache2_run(self):
        result = self.execRun("ls -ld /var/run/apache2")
        self.assertFalse(
            result.find("No such file or directory") > -1,
            msg="/var/run/apache2 is missing"
        )
        self.assertEqual(result[0], 'd', msg="/var/run/apache2 is not a directory")
        self.assertEqual(result[8], 'w', msg="/var/run/apache2 is not a writable by others")

    def test_apache2_mods_enabled(self):
        result = self.execRun("ls -l /etc/apache2/mods-enabled/rewrite.load")
        self.assertFalse(
            result.find("No such file or directory") > -1,
            msg="/etc/apache2/mods-enabled/rewrite.load is missing"
        )
        self.assertEqual(result[0], 'l', msg="rewrite module not enabled")

    def test_apache2_default_site(self):
        result = self.execRun("cat /etc/apache2/sites-available/000-default.conf")
        self.assertFalse(
            result.find("No such file or directory") > -1,
            msg="/etc/apache2/sites-available/000-default.conf is missing"
        )
        self.assertTrue(
            result.find("VirtualHost *:8080") > -1,
            msg="Missing or incorrect VirtualHost entry"
        )
        self.assertTrue(
            result.find("AllowOverride All") > -1,
            msg="Missing AllowOverride All"
        )

    def test_docker_logs(self):
        expected_log_lines = [
            "run-parts: executing /hooks/entrypoint-pre.d/19_doc_root_setup",
            "run-parts: executing /hooks/entrypoint-pre.d/20_ssl_setup",
            "Checking if /var/www/html is empty",
            "Log directory exists"
        ]
        container_logs = self.container.logs().decode('utf-8')
        for expected_log_line in expected_log_lines:
            self.assertTrue(
                container_logs.find(expected_log_line) > -1,
                msg="Docker log line missing: %s from (%s)" % (expected_log_line, container_logs)
            )

    def test_apache2_get(self):
        driver = webdriver.PhantomJS()
        driver.get("http://localhost:8080/test.html")
        self.assertEqual('Success', driver.title)
        #self.screenshot("open")

    def test_apache2_cgi_headers(self):
        # We need to set the desired headers, then get a new driver for this to work
        webdriver.DesiredCapabilities.PHANTOMJS['phantomjs.page.customHeaders.X-Forwarded-For'] = "1.2.3.4"
        webdriver.DesiredCapabilities.PHANTOMJS['phantomjs.page.customHeaders.X-Forwarded-Port'] = "99"
        driver = webdriver.PhantomJS()
        driver.get("http://127.0.0.1:8080/cgi-bin/rpaf.sh")
        self.assertTrue(driver.page_source.find("1.2.3.4") > -1, msg="Missing X-Forwarded-For")
        self.assertTrue(driver.page_source.find("99") > -1, msg="Missing X-Forwarded-Port")
        self.assertEqual(
            self.execRun('bash -c "grep 1.2.3.4 /var/log/apache2/*access_log | grep -iq phantomjs && echo -n true"'),
            "true",
            msg="Missing 1.2.3.4 from logs"
        )

        # </tests to run>

if __name__ == '__main__':
    unittest.main(verbosity=1)
