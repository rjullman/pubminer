from __future__ import print_function
from abc import ABCMeta, abstractmethod
from BeautifulSoup import BeautifulSoup as BS
from argparse import ArgumentParser
from unidecode import unidecode
import itertools
import urllib2
import urllib
import json
import xmltodict
import os
import sys

# ------------------------------------------------------------------------------

class BibliographyMiner:
    """Basic structure for a data miner."""
    __metaclass__ = ABCMeta

    @abstractmethod
    def mine(iden):
        pass

# ------------------------------------------------------------------------------

CACHE_DIRECTORY = "cache/"
def url_to_cache_path(url):
    """Returns a local cache path from a web url"""
    if url.find("http://") != -1:
        url = url[7:]
    return CACHE_DIRECTORY + url

def read_cache(url):
    """Returns the cached string for url or None if url is not cached"""
    path = url_to_cache_path(url)
    try:
        return open(path, "r").read()
    except IOError:
        return None

def cache_page(url, page):
    """Caches the given page string from the given url"""
    path = url_to_cache_path(url)
    directory = os.path.dirname(path)

    # Create the cache directory if necessary
    if not os.path.exists(directory):
       os.makedirs(directory)

    # Write the page to the cache
    f = open(path,'w')
    print(page, file=f)
    f.close()

def url_read(url):
    """Returns a string of the data from the given url.

    Checks the local cache before making a web request.

    """
    page_str = read_cache(url)
    if not page_str:
        print("reading (web):", url, file=sys.stderr)
        page_str = urllib2.urlopen(url).read()
        cache_page(url,page_str)
    else:
        print("reading (cache):", url, file=sys.stderr)

    return page_str

# ------------------------------------------------------------------------------

DBLP_LINK_FORMAT = "http://www.informatik.uni-trier.de/~ley/db/conf/{name}/index.html"
DBLP_YEAR_LINK_FLAG = "http://dblp.uni-trier.de/img/venues.dark.hollow.16x16.png"
class DBLPMiner(BibliographyMiner):
    """Mines bibliographical data from the DBLP cs journal database."""

    def mine(self, iden, filename=None, find_citations=True, limit=30, skip=0):
        # Open output file
        filename = filename if filename else iden + '.dat'
        fout = open(filename, 'w+')

        # Generate url to mine
        url = DBLP_LINK_FORMAT.format(name = iden)

        ## Extract the layers of urls on the dblp website

        # Get the various conference year urls
        year_urls = self._extract_year_urls(url)

        for year_url in year_urls[skip : skip + limit]:
            # Get the urls for the papers in the given conference
            paper_xml_urls = self._extract_paper_xml_urls(year_url)

            # Get the raw xml for the papers
            try:
                xml_dicts = map (lambda x : self._extract_xml_from_url(x), paper_xml_urls)
            except:
                print("failure reading paper xml urls:", paper_xml_urls, file=sys.stderr)

            # Extract the useless wrapper data from the dblp bibliography xml
            f_xml_dicts = filter(lambda x : isinstance(x['title'], unicode),
                                  map(lambda x : x.values()[0].values()[0], xml_dicts))

            # Kick off a request to CiteSeer to finde find the citation the paper uses
            if find_citations:
                citations_list = map(lambda x : CiteSeerMiner().mine(unidecode(x['title'])), f_xml_dicts)
                for i, citations in enumerate(citations_list):
                    if citations:
                        f_xml_dicts[i]['citations'] = citations

            # Write the citations to the file
            map (lambda x : fout.write(json.dumps(x) + '\n'), f_xml_dicts)

        fout.close()

    def _extract_year_urls(self, url):
        """Returns a list of year urls from the given dblp page found at url."""
        parser = BS(url_read(url))
        keyword = url.rsplit('/',2)[1]
        return filter (lambda url : keyword in url,
                       map(lambda x : x.find('a')['href'],
                           filter(lambda x : x.find('img', {'src': DBLP_YEAR_LINK_FLAG}) != None,
                                  parser.findAll('div', {'class': 'head'}))))

    def _extract_paper_xml_urls(self, url):
        """Returns a list of xml paper urls from the given dblp page found at url."""
        parser = BS(url_read(url))
        return map(lambda x : x['href'], 
                   filter(lambda x: x.getText().find("XML") != -1,
                          parser.findAll('a')))

    def _extract_xml_from_url(self, url):
        """Returns a list of xml paper data found at given url."""
        return xmltodict.parse(url_read(url))


CITESEER_DOMAIN = "http://citeseer.ist.psu.edu"
CITESEER_SEARCH_LINK = CITESEER_DOMAIN + "/search?q=title%3A%28{title}%29&sort=cite&t=doc"
CITESEER_DOCUMENT_LINK_PARTIAL = "/viewdoc/"
class CiteSeerMiner(BibliographyMiner):
    def mine(self, iden):
        iden = iden.lower()
        search_url = CITESEER_SEARCH_LINK.format(title = urllib.quote_plus(iden))
        paper_url = self._extract_paper_url(iden, search_url)

        if not paper_url:
            print("citation not found for", iden, file=sys.stderr)
            return None
        else:
            print("citation found for", iden, file=sys.stderr)
            
        try:
            citation_urls = self._extract_citation_urls(paper_url)
        except:
            return None

        authors = map(lambda x : self._extract_citation_from_url(x), citation_urls[0:2])
        return list(itertools.chain(*authors))

    def _extract_paper_url(self, title, url):
        try:
            parser = BS(url_read(url))
            link = parser.find('div', {'class':'result'}).find('h3').find('a')
            search_title = unidecode(link.contents[0].strip().lower())
            if search_title[:len(title)/2] == title[:len(title)/2]:
                return CITESEER_DOMAIN + link['href']
            else:
                return None
        except:
            return None
        
    def _extract_citation_urls(self, url):
        parser = BS(url_read(url))
        return filter(lambda x : CITESEER_DOCUMENT_LINK_PARTIAL in x,
                      map(lambda x : CITESEER_DOMAIN + x['href'], parser.find('div', {'id':'citations'}).findAll('a')))

    def _extract_citation_from_url(self, url):
        parser = BS(url_read(url))
        try:
            return map(lambda s : s.strip(), " ".join(unidecode(parser.find('div', {'id':'docAuthors'}).contents[0]).split())[2:].split(','))
        except:
            return []

# ------------------------------------------------------------------------------

# Setup command line parser
p = ArgumentParser(description="Extacts bibliographic data from DBLP.")
p.add_argument('name', help='the name of the conference to extract')
p.add_argument('-f', dest='file', help='the output file for conference data')
p.add_argument('-l', dest='limit', type=int, default=30, help='number of conference dates to mine (default 30)')
p.add_argument('-s', dest='skip', type=int, default=0, help='number of conference dates (in chronological order) to skip before mining (default 0)')
p.add_argument('-nc', '--nocite', dest='citations', action="store_false", default=True, help='disable citation mining from CiteSeer')
args = p.parse_args()

# Kick off the data mining
miner = DBLPMiner()
miner.mine(args.name, find_citations=args.citations, filename=args.file, limit=args.limit, skip=args.skip)
