#!/usr/bin/env python3

import unittest
import os
import docker
from selenium import webdriver
import os.path
import tarfile
from io import BytesIO
from testpack_helper_library.unittests.dockertests import Test1and1Common


class Test1and1ApacheImage(Test1and1Common):
    container_ip = None

    @classmethod
    def setUpClass(cls):
        Test1and1Common.setUpClass()
        Test1and1ApacheImage.copy_test_files("testpack/files", "html", "/var/www")
        details = docker.APIClient().inspect_container(container=Test1and1Common.container.id)
        Test1and1ApacheImage.container_ip = details['NetworkSettings']['IPAddress']

    @classmethod
    def copy_test_files(cls, startfolder, relative_source, dest):
        # Change to the start folder
        pwd = os.getcwd()
        os.chdir(startfolder)
        # Tar up the request folder
        pw_tarstream = BytesIO()
        with tarfile.open(fileobj=pw_tarstream, mode='w:gz') as tf:
            tf.add(relative_source)
        # Copy the archive to the correct destination
        docker.APIClient().put_archive(
            container=Test1and1Common.container.id,
            path=dest,
            data=pw_tarstream.getvalue()
        )
        # Change back to original folder
        os.chdir(pwd)

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
        driver.get("http://%s:8080/test.html" % Test1and1ApacheImage.container_ip)
        self.assertEqual('Success', driver.title)
        #self.screenshot("open")

    def test_apache2_cgi_headers(self):
        # We need to set the desired headers, then get a new driver for this to work
        webdriver.DesiredCapabilities.PHANTOMJS['phantomjs.page.customHeaders.X-Forwarded-For'] = "1.2.3.4"
        webdriver.DesiredCapabilities.PHANTOMJS['phantomjs.page.customHeaders.X-Forwarded-Port'] = "99"
        driver = webdriver.PhantomJS()
        driver.get("http://%s:8080/cgi-bin/rpaf.sh" % Test1and1ApacheImage.container_ip)
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
