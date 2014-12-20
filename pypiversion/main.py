#!/usr/bin/env python

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# author: Christian Berendt <mail@cberendt.net>

import argparse
from bs4 import BeautifulSoup
import datetime
from distutils.version import StrictVersion
import hashlib
import jinja2
import logging
import os
import PyRSS2Gen
import sys
import xmlrpclib
import yaml


def initialize_logging():
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)


def parse_command_line_arguments():
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("category", type=str, default=None,
                        help="The category that should be used.")
    parser.add_argument("path", type=str, default=None,
                        help="The path to the template and configuration file.")
    return parser.parse_args()


def get_template(template):
    loader = jinja2.FileSystemLoader(os.path.dirname(template))
    environment = jinja2.Environment(loader=loader)
    return environment.get_template(os.path.basename(template))


def load_configuration(configuration):
    return yaml.load(open(configuration))


def get_connection():
    return xmlrpclib.ServerProxy('https://pypi.python.org/pypi', allow_none=True)


def main():

    initialize_logging()
    args = parse_command_line_arguments()

    filename_configuration = os.path.join( 
        args.path,
        "openstack_%s_versions.yaml" % args.category
    )

    filename_html = os.path.join(args.path,
                                 "openstack_%s_versions.html" % args.category)
    filename_feed = os.path.join(args.path,
                                 "openstack_%s_versions.xml" % args.category)

    packages = load_configuration(filename_configuration)
    template = get_template(os.path.join(args.path, "pypi_versions.tmpl"))
    client = get_connection()

    rss = PyRSS2Gen.RSS2(
        title="OpenStack %s packages on PyPi" % args.category,
        link="http://ghostcloud.net/openstack_%s_versions.html" % args.category,
        description="The latest available OpenStack %s packages on PyPi." % args.category,
        lastBuildDate=datetime.datetime.now()
    )

    for package in packages.iterkeys():
        logging.debug("checking package %s" % package)

        releases = client.package_releases(package, True)
        if len(releases) > 0:
            urls = client.release_urls(package, releases[0])
            if len(urls) == 0:
                continue
            packages[package]['version'] = releases[0]
            data = client.release_data(package, packages[package]['version'])
            if urls[0]["upload_time"]:
                upload_time = datetime.datetime.strptime(str(urls[0]["upload_time"]), "%Y%m%dT%H:%M:%S")
                diff = datetime.datetime.utcnow() - upload_time
                packages[package]['days_ago'] = diff.days
                packages[package]['upload_time'] = datetime.datetime.strftime(upload_time, "%Y-%m-%d %H:%M:%S")
            packages[package]['release_url'] = data['release_url']
            packages[package]['author'] = data['author']
            packages[package]['url'] = urls[0]["url"]
            if packages[package]['url'].endswith('.whl'):
                packages[package]['url'] = urls[1]["url"]
            packages[package]['package_url'] = data["package_url"]
            packages[package]['filename'] = os.path.basename(packages[package]['url'])
            packages[package]['summary'] = data["summary"]

            checksum = hashlib.md5()
            checksum.update("%s-%s" % (package, packages[package]['version']))

            item = PyRSS2Gen.RSSItem(
                title="%s - %s" % (package, packages[package]['version']),
                author=packages[package]['author'],
                link=packages[package]['release_url'],
                guid=PyRSS2Gen.Guid(checksum.hexdigest()),
                description=packages[package]['summary'],
                pubDate=packages[package]['upload_time'],
            )
            rss.items.append(item)

    with open(filename_configuration, 'w') as outfile:
        outfile.write(yaml.dump(packages, default_flow_style=False))

    output = template.render({
        'packages': packages,
        'timestamp': datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        'title': args.category})

    with open(filename_html, 'w') as outfile:
        soup = BeautifulSoup(output)
        outfile.write(soup.prettify())
    with open(filename_feed, 'w') as outfile:
        outfile.write(rss.to_xml())

    return 0


if __name__ == '__main__':
    sys.exit(main())
