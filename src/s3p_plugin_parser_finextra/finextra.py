import copy
import time
from typing import Iterator

import dateparser
import dateutil.parser
import feedparser
from s3p_sdk.exceptions.parser import S3PPluginParserOutOfRestrictionException, S3PPluginParserFinish
from s3p_sdk.plugin.payloads.parsers import S3PParserBase
from s3p_sdk.types import S3PRefer, S3PDocument, S3PPlugin, S3PPluginRestrictions
from s3p_sdk.types.plugin_restrictions import FROM_DATE
import requests
from bs4 import BeautifulSoup
from random import randint


class Finextra(S3PParserBase):
    """
    A Parser payload that uses S3P Parser base class.
    """

    def __init__(self, refer: S3PRefer, plugin: S3PPlugin, restrictions: S3PPluginRestrictions, feeds: list[str, ...]):
        super().__init__(refer, plugin, restrictions)

        # Тут должны быть инициализированы свойства, характерные для этого парсера. Например: WebDriver
        self.feeds = feeds

    def _parse(self):
        """
        Парсер сначала получает document из фидов. После запроса страницы передаёт в document.other
        словарь "general", куда добавляется текст, возвращаемый find_text, а затем словарь
        "additionals_dict", возвращаемый find_additions.
        """
        if isinstance(self._restriction.maximum_materials, int) and self._restriction.maximum_materials // len(
                self.feeds) >= 2:
            number = self._restriction.maximum_materials // len(self.feeds) + 1
        else:
            number = None

        for feed in self.feeds:
            for document in self._slices(
                self._rss_feed(feed),
                number
            ):
                time.sleep(randint(1,3))
                self._parsed_webpage(document)
                try:
                    self._find(document)
                except S3PPluginParserOutOfRestrictionException as e:
                    self.logger.warning(f"Document {document.id} is outside the specified date range")
                    if e.restriction == FROM_DATE:
                        break
                except S3PPluginParserFinish as e:
                    raise e

    def _slices(self, feed: Iterator[S3PDocument], number: int | None = None) -> Iterator[S3PDocument]:
        for current, element in enumerate(feed):
            if number is not None and current >= number:
                break
            yield element

    def _rss_feed(self, url: str) -> Iterator[S3PDocument]:
        """
        url: str: RSS FEED url
        """
        # Parse the Finextra RSS feed
        feed = feedparser.parse(url)

        # Iterate through feed entries
        for entry in feed.entries:
            parsed_date = dateutil.parser.parse(entry.published)

            yield S3PDocument(
                None,
                entry.title,
                None,
                None,
                entry.link,
                None,
                {
                    'summary': entry.summary if 'summary' in entry else None,
                },
                parsed_date.replace(tzinfo=None),
                None,
            )

    def _parsed_webpage(self, document: S3PDocument) -> S3PDocument | None:
        #Делаем запрос к странице
        response = requests.get(document.link)
        if response.status_code != 200:
            raise ConnectionError(f"Failed to access {self.max_bad_requests} pages. Status code: {response.status_code}")

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        try:
            return Finextra.ArticlePage(soup, document).document()
        except Finextra.PageException:
            ...
        try:
            return Finextra.WebinarPage(soup, document).document()
        except Finextra.PageException:
            ...

        raise ValueError(f'{document.link} not parsed. Profile is not exist')

    class PageException(Exception):

        def __init__(self, profile, message, errors=None):
            super().__init__(message)
            self.errors = errors
            self.profile = profile
            self.message = message

        def __repr__(self):
            return f"Profile {type(self.profile)} Not found"

    class ArticlePage:
        META: str = 'Article'

        def __init__(self, soup, document: S3PDocument):
            self.soup = soup
            self.doc = copy.deepcopy(document)
            self.doc.other['type'] = self.META

        def document(self) -> S3PDocument:
            # Main article text
            article_body = self.soup.find('div', class_='alt-body-copy')
            if article_body is None:
                raise Finextra.PageException(self, f'', None)
            else:
                article_text = '\n'.join([p.get_text(strip=True) for p in article_body.find_all('p')])
                self.doc.text = article_text

            # Additional fields
            types_additions = ['company', 'channel', 'keyword']
            additional_section = self.soup.find('div', class_='additional-info')
            additional_dict = {}
            if additional_section is not None:
                for addition_name in types_additions:
                    # Проверяем, существует ли хотя бы один элемент с классом .info-icon.{addition_name}
                    elements = additional_section.select(f'.info-icon.{addition_name} a')
                    if elements:  # Если список не пуст
                        additional_dict[addition_name] = [a.get_text(strip=True) for a in elements]
                if additional_dict != {}:
                    self.doc.other['general'] = additional_dict

            return self.doc

    class WebinarPage:
        META: str = 'Webinar'

        def __init__(self, soup, document: S3PDocument):
            self.soup = soup
            self.doc = copy.deepcopy(document)
            self.doc.other['type'] = self.META

        def document(self) -> S3PDocument:
            # Main Webinar Text
            event_summary_article_body = self.soup.find('div', class_='event-summary alt-body-copy')
            if event_summary_article_body is None:
                raise Finextra.PageException(self, f'', None)
            else:
                thesis = [p.get_text(strip=True) for p in event_summary_article_body.find_all('li')]
                text = [p.get_text(strip=True) for p in event_summary_article_body.find_all('p')]
                summary = ''
                if thesis:
                    summary += '\n'.join(thesis)
                if text:
                    if thesis:
                        summary += '\n'
                    summary += '\n'.join(text)
                self.doc.text = summary

            # Speakers (Optional)
            if sp := self.speakers():
                self.doc.other['other'] = sp

            return self.doc

        def speakers(self) -> dict | None:
            speakers_section = self.soup.find('div', {'id': 'ctl00_ctl00_body_main_SummaryForm_hSpeakers'})
            additional_dict = {}
            speakers = []
            if speakers_section is not None:
                for speaker in speakers_section.find_all('li', class_='event-speakers-people-container'):
                    name = speaker.find('h4', class_='event-speakers-people-text-title').text.strip()
                    activity = speaker.find('p').text.strip()
                    speakers.append([name, activity])
                additional_dict['speakers'] = speakers
                return additional_dict
            return None