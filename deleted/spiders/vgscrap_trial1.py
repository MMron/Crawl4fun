#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

class MySpider(scrapy.Spider):
    name = 'vg crawler'
    allowed_domains = ['vg.no']
    start_urls = [
        'https://www.vg.no/nyheter'
    ]

    
    def start_requests(self):
        self.data = {'text':[], 'title':[], 'url':[], 'pub_date':[]}
        self.no_page = 0
        self.no_deep_dives = 0
        self.max_dives = np.inf

        yield scrapy.Request('https://www.vg.no/nyheter', self.first_parse)

    def first_parse(self, response):
        #TEXT_SELECTOR = '._3Lrvz _1Q79c'
        #print(response.xpath('//div[@class="_3Lrvz _1Q79c"]/p/text()').extract())
        #.xpath('//div[@class="ld-header"]/h1/text()').extract()
        #print(response.url)

        self.logger.info('A response from %s just arrived!', response.url)
        


        NEXT_PAGE_SELECTOR = '.css-1x7sjhy a ::attr(href)'
        next_pages = response.css(NEXT_PAGE_SELECTOR).extract()
        print(next_pages)
        
        self.no_pages = len(next_pages)
        
        for next_page in next_pages:
            print(next_page)
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
            self.data['pub_date'].append(pub_date)
        elif pub_date_raw_dp:
            pub_date = self._converter_mht(list(set(pub_date_raw_dp))[0],'yyyy-mm-ddThh:mm:ssZ')
            self.data['pub_date'].append(pub_date)
        else:
            print('no date available:')
            print(response.url)
            
            
#            <time itemprop="datePublished" datetime="2020-01-17T08:03:04Z" aria-label="Publisert: 17.01.20 kl. 09:03">I dag 09:03</time>
  
        self.data['url'].append(response.url)
        self.data['text'].append(whole_text)
        self.data['title'].append(title)
        
        if self.no_deep_dives<self.max_dives:
            new_links = response.css('a[data-test-tag="teaser-small:link-internal"]::attr(href)').extract()
            print('new links arrived: ')
            print(type(new_links))
            print(new_links)


        if new_links:
            self.no_deep_dives+=1
            self.no_pages += len(set(new_links)-set(self.data['url']))
            for next_page in new_links:
                if self._valid_url(response.urljoin(next_page)):
                    print('in deep dig')
                    print(next_page)
                    yield scrapy.Request(
                    response.urljoin(next_page),
                    callback=self.parse
                    )

        if (self.no_page == self.no_pages-1):# and (self.no_deep_dives==self.max_dives):
            print(f'number of pages stored {self.no_pages}, number of pages crawled {self.no_page}, number of dives:{self.no_deep_dives}')
            now = datetime.now()
            print(f'length of dataframe{len(self.data["url"])}')
            date_now = now.strftime("%y.%m.%d %H:%M:%S")
            with open('./data/vg/' +'test'+'.pickle', "wb" ) as handle:
                pickle.dump(self.data, handle)
        
        
        
        #<a data-test-tag="teaser-small:link-internal" href="/nyheter/innenriks/i/wPLrlA/flere-partitopper-for-frp-exit-jeg-er-mektig-lei?utm_source=inline-teaser&amp;utm_content=wPL3e5" class="_6cKEc _3v6UN _3j0HF inline nolinkstyles" rel="" target="" aria-label="Flere partitopper for «Frp-exit»: – Jeg er mektig lei"><div><div class="LeIVf _1R5ui">les også</div><h2 class="_2oNDx _1eFyf _2G45I OR7W2">Flere partitopper for «Frp-exit»: – Jeg er mektig lei</h2></div></a>
    def _valid_url(self, new_url):
        """
        
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
        
        
        
    def _process_mht(self, text):
        whole_text = ''
        for line in text:
            parsed = re.search(r'>(.*?)<', line).group(1)
            whole_text +=parsed#+'\n'
        return whole_text

    def _converter_mht(self,gg, fmat = 'yyyy-mm-dd hh:mm:ss'):
        if fmat == 'yyyy-mm-ddThh:mm:ssZ':
            date = gg[:9]+' '+gg[11:-1]
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
