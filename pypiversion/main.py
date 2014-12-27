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
from datetime import datetime  # noqa
import hashlib
import logging
import os
import sys
import xmlrpclib  # noqa

from bs4 import BeautifulSoup
import jinja2
import PyRSS2Gen
import yaml


def initialize_logging():
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)


def parse_command_line_arguments():
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("configuration", type=str, default=None,
                        help="Path to configuration file.")
    return parser.parse_args()


def get_template(template):
    loader = jinja2.FileSystemLoader(os.path.dirname(template))
    environment = jinja2.Environment(loader=loader)
    return environment.get_template(os.path.basename(template))


def get_connection():
    return xmlrpclib.ServerProxy('https://pypi.python.org/pypi',
                                 allow_none=True)


def main():

    initialize_logging()
    args = parse_command_line_arguments()
    configuration = yaml.load(open(args.configuration))
    template = get_template(os.path.join(configuration['basepath'],
                                         configuration['files']['template']))
    file_feed = os.path.basename(configuration['files']['feed'])
    file_yaml = os.path.basename(configuration['files']['yaml'])
    file_html = os.path.basename(configuration['files']['html'])
    client = get_connection()

    rss = PyRSS2Gen.RSS2(
        title=configuration['title'],
        link="%s/%s" % (configuration['baseurl'], file_html),
        description=configuration['description'],
        lastBuildDate=datetime.now()
    )

    packages = {}
    for package in configuration['packages']:
        logging.debug("checking package %s" % package)

        releases = client.package_releases(package, True)
        if len(releases) > 0:
            urls = client.release_urls(package, releases[0])
            if len(urls) == 0:
                continue
            packages[package] = {}
            packages[package]['version'] = releases[0]
            data = client.release_data(package, packages[package]['version'])
            if urls[0]["upload_time"]:
                upload_time = datetime.strptime(str(urls[0]["upload_time"]),
                                                "%Y%m%dT%H:%M:%S")
                diff = datetime.utcnow() - upload_time
                packages[package]['days_ago'] = diff.days
                packages[package]['upload_time'] = datetime.strftime(
                    upload_time, "%Y-%m-%d %H:%M:%S")
            packages[package]['release_url'] = data['release_url']
            packages[package]['author'] = data['author']
            packages[package]['url'] = urls[0]["url"]
            if packages[package]['url'].endswith('.whl') and len(urls) > 1:
                packages[package]['url'] = urls[1]["url"]
            packages[package]['package_url'] = data["package_url"]
            packages[package]['filename'] = os.path.basename(
                packages[package]['url'])
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

    output = template.render({
        'packages': packages,
        'timestamp': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        'title': configuration['title'],
        'description': configuration['description'],
        'url_feed': "%s/%s" % (configuration['baseurl'], file_feed),
        'url_yaml': "%s/%s" % (configuration['baseurl'], file_yaml),
        'url_html': "%s/%s" % (configuration['baseurl'], file_html)
    })

    if 'yaml' in configuration['files']:
        file_yaml = os.path.join(configuration['basepath'],
                                 configuration['files']['yaml'])
        with open(file_yaml, 'w') as outfile:
            outfile.write(yaml.dump(packages, default_flow_style=False))

    if 'html' in configuration['files']:
        file_html = os.path.join(configuration['basepath'],
                                 configuration['files']['html'])
        with open(file_html, 'w') as outfile:
            soup = BeautifulSoup(output)
            outfile.write(soup.prettify())

    if 'feed' in configuration['files']:
        file_feed = os.path.join(configuration['basepath'],
                                 configuration['files']['feed'])
        with open(file_feed, 'w') as outfile:
            outfile.write(rss.to_xml())

    return 0


if __name__ == '__main__':
    sys.exit(main())
