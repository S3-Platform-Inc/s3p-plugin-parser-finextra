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
        self.types_additions = ['company', 'channel', 'keyword']

    def find_additions(self, soup, document):
        # Ищем секцию с дополнительной информацией
        additional_section = soup.find('div', class_='additional-info')
        speakers_section = soup.find('div', {'id': 'ctl00_ctl00_body_main_SummaryForm_hSpeakers'})
        additionals_dict = {}
        speakers = []

        if additional_section:
            for addition_name in self.types_additions:
                # Проверяем, существует ли хотя бы один элемент с классом .info-icon.{addition_name}
                elements = additional_section.select(f'.info-icon.{addition_name} a')
                if elements:  # Если список не пуст
                    additionals_dict[addition_name] = [a.get_text(strip=True) for a in elements]
                else:
                    # Если элементы отсутствуют, можно добавить пустой список или другое значение по умолчанию
                    additionals_dict[addition_name] = []
            return(additionals_dict)
        elif speakers_section:
            for speaker in speakers_section.find_all('li', class_='event-speakers-people-container'):
                name = speaker.find('h4', class_='event-speakers-people-text-title').text.strip()
                activity = speaker.find('p').text.strip()
                speakers.append([name, activity])
                additionals_dict['speakers'] = speakers
            return(additionals_dict)
        else:
            print(document.link)

    def find_text(self, soup, document):
        # Ищем блок с текстом статьи
        article_body = soup.find('div', class_='alt-body-copy')
        event_summary_article_body = soup.find('div', class_='event-summary alt-body-copy')

        if article_body:
            article_text = '\n'.join([p.get_text(strip=True) for p in article_body.find_all('p')])
            return(article_text)
        elif event_summary_article_body:
            summary_text = '\n'.join([p.get_text(strip=True) for p in event_summary_article_body.find_all('li')])
            summary_text += '\n'
            summary_text += '\n'.join([p.get_text(strip=True) for p in event_summary_article_body.find_all('p')])
            return (summary_text)
        else:
            raise ValueError(f"Article text block not found: {document.link}")

    def _parse(self):
        """
        Функция find_additions ищет доп. информацию на сайте (related company, channels и т.д.).
        Иногда на сайте нет доп. информации, соответствующей types_additions. На некоторых URL
        вместо неё могут быть спикеры вебинаров или просто текст (webinar).
        Поэтому сначала проверяем наличие таких блоков на странице и действуем в зависимости от
        их наличия (либо ничего не делаем, либо берём спикеров вместо доп. информации).

        Функция find_text ищет блок текста статьи. Если на странице нет блока1(article_body), проверяем наличие
        блока2(event_summary_article_body). Если есть блок2, сначала извлекаем вопросы из начала статьи, добавляем абзац, а
        затем берём основной текст статьи.

        Парсер сначала получает document из фидов. После запроса страницы передаёт в document.other
        словарь "general", куда добавляется текст, возвращаемый find_text, а затем словарь
        "additionals_dict", возвращаемый find_additions.
        """

        if isinstance(self._restriction.maximum_materials, int) and self._restriction.maximum_materials // len(
                self.feeds) >= 4:
            number = self._restriction.maximum_materials // len(self.feeds) + 1
        else:
            number = None

        for feed in self.feeds:
            for document in self._slices(
                    self._rss_feed(
                        feed
                    ),
                    number
            ):
                 time.sleep(randint(1,3))
                 # Делаем запрос к странице
                 response = requests.get(document.link)
                 if response.status_code != 200:
                     raise ValueError(f"Failed to access the page. Status code: {response.status_code}")

                 html = response.text
                 soup = BeautifulSoup(html, 'html.parser')

                 document.other['general'] = {}
                 document.other['general']['text'] = self.find_text(soup, document)
                 document.other['general'] = self.find_additions(soup, document)


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