# Mobile Verification Toolkit (MVT)
# Copyright (c) 2021 MVT Project Developers.
# See the file 'LICENSE' for usage and copying permissions, or find a copy at
#   https://github.com/mvt-project/mvt/blob/main/LICENSE

import json
import os

from .url import URL


class Indicators:
    """This class is used to parse indicators from a STIX2 file and provide
    functions to compare extracted artifacts to the indicators.
    """

    def __init__(self, file_path, log=None):
        self.file_path = file_path
        with open(self.file_path, "r") as handle:
            self.data = json.load(handle)

        self.log = log
        self.ioc_domains = []
        self.ioc_processes = []
        self.ioc_emails = []
        self.ioc_files = []
        self._parse_stix_file()

    def _parse_stix_file(self):
        """Extract IOCs of given type from STIX2 definitions.
        """
        for entry in self.data["objects"]:
            try:
                if entry["type"] != "indicator":
                    continue
            except KeyError:
                continue

            key, value = entry["pattern"].strip("[]").split("=")
            value = value.strip("'")

            if key == "domain-name:value":
                # We force domain names to lower case.
                value = value.lower()
                if value not in self.ioc_domains:
                    self.ioc_domains.append(value)
            elif key == "process:name":
                if value not in self.ioc_processes:
                    self.ioc_processes.append(value)
            elif key == "email-addr:value":
                # We force email addresses to lower case.
                value = value.lower()
                if value not in self.ioc_emails:
                    self.ioc_emails.append(value)
            elif key == "file:name":
                if value not in self.ioc_files:
                    self.ioc_files.append(value)

    def check_domain(self, url):
        # TODO: If the IOC domain contains a subdomain, it is not currently
        # being matched.

        try:
            # First we use the provided URL.
            orig_url = URL(url)

            if orig_url.check_if_shortened():
                # If it is, we try to retrieve the actual URL making an
                # HTTP HEAD request.
                unshortened = orig_url.unshorten()

                # self.log.info("Found a shortened URL %s -> %s",
                #               url, unshortened)

                # Now we check for any nested URL shorteners.
                dest_url = URL(unshortened)
                if dest_url.check_if_shortened():
                    # self.log.info("Original URL %s appears to shorten another shortened URL %s ... checking!",
                    #               orig_url.url, dest_url.url)
                    return self.check_domain(dest_url.url)

                final_url = dest_url
            else:
                # If it's not shortened, we just use the original URL object.
                final_url = orig_url
        except Exception as e:
            # If URL parsing failed, we just try to do a simple substring
            # match.
            for ioc in self.ioc_domains:
                if ioc.lower() in url:
                    self.log.warning("Maybe found a known suspicious domain: %s", url)
                    return True

            # If nothing matched, we can quit here.
            return False

        # If all parsing worked, we start walking through available domain indicators.
        for ioc in self.ioc_domains:
            # First we check the full domain.
            if final_url.domain.lower() == ioc:
                if orig_url.is_shortened and orig_url.url != final_url.url:
                    self.log.warning("Found a known suspicious domain %s shortened as %s",
                                     final_url.url, orig_url.url)
                else:
                    self.log.warning("Found a known suspicious domain: %s", final_url.url)

                return True

            # Then we just check the top level domain.
            if final_url.top_level.lower() == ioc:
                if orig_url.is_shortened and orig_url.url != final_url.url:
                    self.log.warning("Found a sub-domain matching a suspicious top level %s shortened as %s",
                                     final_url.url, orig_url.url)
                else:
                    self.log.warning("Found a sub-domain matching a suspicious top level: %s", final_url.url)

                return True

    def check_domains(self, urls):
        """Check the provided list of (suspicious) domains against a list of URLs.
        :param urls: List of URLs to check
        """
        for url in urls:
            if self.check_domain(url):
                return True

    def check_process(self, process):
        """Check the provided process name against the list of process
        indicators.
        :param process: Process name to check
        """
        if not process:
            return False

        proc_name = os.path.basename(process)
        if proc_name in self.ioc_processes:
            self.log.warning("Found a known suspicious process name \"%s\"", process)
            return True

        if len(proc_name) == 16:
            for bad_proc in self.ioc_processes:
                if bad_proc.startswith(proc_name):
                    self.log.warning("Found a truncated known suspicious process name \"%s\"", process)
                    return True

    def check_processes(self, processes):
        """Check the provided list of processes against the list of
        process indicators.
        :param processes: List of processes to check
        """
        for process in processes:
            if self.check_process(process):
                return True

    def check_email(self, email):
        """Check the provided email against the list of email indicators.
        :param email: Suspicious email to check
        """
        if not email:
            return False

        if email.lower() in self.ioc_emails:
            self.log.warning("Found a known suspicious email address: \"%s\"", email)
            return True

    def check_file(self, file_path):
        """Check the provided file path against the list of file indicators.
        :param file_path: Path or name of the file to check
        """
        if not file_path:
            return False

        file_name = os.path.basename(file_path)
        if file_name in self.ioc_files:
            self.log.warning("Found a known suspicious file: \"%s\"", file_path)
            return True
