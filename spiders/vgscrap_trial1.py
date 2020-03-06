"""
Created on Thu Jan 16 12:52:24 2020

@author: meronhailetesfazion
"""

import scrapy
import scrapy.crawler as crawler
from twisted.internet import reactor
from scrapy.crawler import CrawlerProcess, CrawlerRunner
import os
import re
from scrapy.selector import Selector
from multiprocessing import Process, Queue
import pickle
from datetime import datetime
import numpy as np
from scrapy.utils.test import get_crawler


class MySpider(scrapy.Spider):
    name = 'vg crawler'
    allowed_domains = ['vg.no/nyhter']
    start_urls = [f'https://www.vg.no/nyheter/?pageId={f}' for f in range(250)]
    
    #[
    #    'https://www.vg.no/nyheter'
    #]

    def start_requests(self):
        self.data = {'text':[], 'title':[], 'url':[], 'pub_date':[]}
        self.no_page = 0
        self.no_deep_dives = 0
        self.max_dives = np.inf
        self.store_folder = "/Users/meronhailetesfazion/Developer/Crawl4fun/spiders/data/vg/"

        yield scrapy.Request('https://www.vg.no/nyheter', self.first_parse)

    def first_parse(self, response):

        self.logger.info('A response from %s just arrived!', response.url)

        NEXT_PAGE_SELECTOR = '.css-1x7sjhy a ::attr(href)' # first class is .css-1x7sjhy then a subsequent class, with href inside
        next_pages = response.css(NEXT_PAGE_SELECTOR).extract()
        
        self.no_pages = len(next_pages)
        
        for next_page in next_pages:
            self._in_deep = 0
            yield scrapy.Request(
                response.urljoin(next_page),
                callback=self.parse
            )

            
            
    def parse(self, response):
        self.no_page +=1
        new_links = False
        hxs = Selector(response)        
        paragraphs = hxs.xpath('//p[@class="_3Lrvz _1Q79c"]').extract()
        whole_text = self._process_mht(paragraphs)
        title = hxs.xpath('//title/text()').get()
        pub_date_raw_dm = response.css('time[itemprop=dateModified]::attr(datetime)').extract()
        pub_date_raw_dp = response.css('time[itemprop=datePublished]::attr(datetime)').extract()
        if pub_date_raw_dm:
            pub_date = self._converter_mht(list(set(pub_date_raw_dm))[0],'yyyy-mm-ddThh:mm:ssZ')
        elif pub_date_raw_dp:
            pub_date = self._converter_mht(list(set(pub_date_raw_dp))[0],'yyyy-mm-ddThh:mm:ssZ')
        else:
            print('no date available:')
            print(response.url)
            
  
        self.data['url'].append(response.url if response.url else 'None')
        self.data['text'].append(whole_text if whole_text else 'None')
        self.data['title'].append(title if title else 'None')
        self.data['pub_date'].append(pub_date if pub_date else 'None')

        if self.no_deep_dives < self.max_dives:
            new_links = response.css('a[data-test-tag="teaser-small:link-internal"]::attr(href)').extract()
            more_links = response.css('li[class="_2q2-Z"]::attr(href)').extract()
            if more_links:
                print('MOOORE LINKS!')
                print(more_links)
                self.logger.info('number of more links: {0}'.format(len(more_links)))
                new_links.append(more_links)

        if new_links:
            self.no_deep_dives+=1
            for next_page in list(set(new_links)):
                if self._valid_url(response.urljoin(next_page)):
                    yield scrapy.Request(
                    response.urljoin(next_page),
                    callback=self.parse
                    )
        
        
    def _valid_url(self, new_url):
        """
        Check if the Url is not already a part of the data stored
        
        """
        return new_url not in self.data['url']        
        
        
    def _deep_dig(self, response, new_links):
        """
        
        """
        if new_links:
            self.no_pages += len(new_links)
            print('in deep dig')
            print(new_links)
            for next_page in new_links:
                yield scrapy.Request(
                response.urljoin(next_page),
                callback=self.parse
                )
    def closed(self, reason):
        """
        Method initiated at the end of the crawler 
        """
        now = datetime.now()
        date_now = now.strftime("%y.%m.%d %H:%M:%S").replace(' ','_')
        with open(self.store_folder +date_now+'.pickle', "wb" ) as handle:
            pickle.dump(self.data, handle)
        
    def _process_mht(self, text):
        whole_text = ''
        for line in text:
            parsed = re.search(r'>(.*?)<', line).group(1)
            whole_text +=parsed#+'\n'
        return whole_text

    def _converter_mht(self,gg, fmat = 'yyyy-mm-dd hh:mm:ss'):
        if fmat == 'yyyy-mm-ddThh:mm:ssZ':
            date = gg[:10]+' '+gg[11:-1]
        elif fmat == 'yyyy-mm-dd hh:mm:ss':
            date = gg
        
        return date


# the wrapper to make it run more times
def run_spider(spider):
    def f(q):
        try:
            runner = crawler.CrawlerRunner()
            deferred = runner.crawl(spider)
            deferred.addBoth(lambda _: reactor.stop())
            reactor.run()
            q.put(None)
        except Exception as e:
            q.put(e)

    q = Queue()
    p = Process(target=f, args=(q,))
    p.start()
    result = q.get()
    p.join()

    if result is not None:
        raise result
        
if __name__ == "__main__": # /anaconda3/envs/funny/bin/python
    process = CrawlerProcess(settings={
        'FEED_FORMAT': 'json',
        'FEED_URI': 'items.json'
    })
    runner = CrawlerRunner()

    d = runner.crawl(MySpider)
    d.addBoth(lambda _: reactor.stop())
    reactor.run() # the script will block here until the crawling is finished

