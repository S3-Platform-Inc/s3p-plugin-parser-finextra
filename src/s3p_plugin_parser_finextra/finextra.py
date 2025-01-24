from datetime import timedelta, datetime
import time
import dateparser
from s3p_sdk.exceptions.parser import S3PPluginParserOutOfRestrictionException, S3PPluginParserFinish
from s3p_sdk.plugin.payloads.parsers import S3PParserBase
from s3p_sdk.types import S3PRefer, S3PDocument, S3PPlugin, S3PPluginRestrictions
from s3p_sdk.types.plugin_restrictions import FROM_DATE
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common import TimeoutException


class Finextra(S3PParserBase):
    """
    A Parser payload that uses S3P Parser base class.
    """

    def __init__(self, refer: S3PRefer, plugin: S3PPlugin, restrictions: S3PPluginRestrictions, web_driver: WebDriver, host: str):
        super().__init__(refer, plugin, restrictions)

        # Тут должны быть инициализированы свойства, характерные для этого парсера. Например: WebDriver
        self._driver = web_driver
        self.HOST = host
        self._wait = WebDriverWait(self._driver, timeout=20)

    def _parse(self):
        """
        Метод, занимающийся парсингом. Он добавляет в _content_document документы, которые получилось обработать
        :return:
        :rtype:
        """
        # HOST - это главная ссылка на источник, по которому будет "бегать" парсер
        self.logger.debug(F"Parser enter to {self.HOST}")

        # ========================================
        # Тут должен находится блок кода, отвечающий за парсинг конкретного источника
        # -
        current_date = datetime(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
        # end_date = current_date - self.interval
        self.logger.info(f"Текущая дата: {datetime.strftime(current_date, '%Y-%m-%d')}")
        # self.logger.info(
        #     f"Окончательная дата: {datetime.strftime(end_date, '%Y-%m-%d')} (разница в днях: {self.interval})")

        while True:
            page_link = f"https://www.finextra.com/latest-news?date={datetime.strftime(current_date, '%Y-%m-%d')}"
            try:
                self.logger.info(f'Загрузка: {page_link}')
                self._driver.get(page_link)
                self._wait.until(ec.presence_of_element_located((By.CLASS_NAME, 'card-body')))
            except:
                self.logger.info('TimeoutException:',
                                 f"https://www.finextra.com/latest-news?date={datetime.strftime(current_date, '%Y-%m-%d')}")
                current_date = current_date - timedelta(1)
                self.logger.debug(f"Изменение даты на новую: {datetime.strftime(current_date, '%Y-%m-%d')}")
                continue
            time.sleep(1)

            # Цикл по новостям за определенную дату
            while True:
                articles = self._driver.find_elements(By.XPATH, "//*[contains(@class, 'card-title')]/a")

                for article in articles:
                    article_url = article.get_attribute('href')

                    self.logger.info(f'Загрузка и обработка документа: {article_url}')
                    self._driver.execute_script("window.open('');")
                    self._driver.switch_to.window(self._driver.window_handles[1])

                    try:
                        self._driver.get(article_url)
                        self._wait.until(ec.presence_of_element_located((By.CLASS_NAME, 'article-content')))
                    except TimeoutException:
                        self.logger.info(f'TimeoutException: {article_url}')
                        self.logger.info('Закрытие вкладки и переход к след. материалу...')
                        self._driver.close()
                        self._driver.switch_to.window(self._driver.window_handles[0])
                        continue

                    time.sleep(1)

                    try:
                        title = self._driver.find_element(By.XPATH,
                                                          "//div[contains(@class, 'article-content')]/h1").text
                        article_type = self._driver.current_url.split('/')[3]
                        # title = article_title.find_element(By.TAG_NAME, 'h1').text
                        date_text = self._driver.find_element(By.XPATH,
                                                              "//p[contains(@class, 'card-baseline')]/time").get_attribute(
                            'datetime')

                        date = dateparser.parse(date_text)
                        tw_count = 0  # article_title.find_element(By.CLASS_NAME, 'module--share-this').find_element(By.ID,'twitterResult').text
                        li_count = 0  # article_title.find_element(By.CLASS_NAME, 'module--share-this').find_element(By.ID,'liResult').text
                        fb_count = 0  # article_title.find_element(By.CLASS_NAME, 'module--share-this').find_element(By.ID,'fbResult').text

                        left_tags = ''  # self._driver.find_element(By.CLASS_NAME, 'article--tagging-left')

                        try:
                            related_comp = ', '.join([el.text for el in left_tags.find_elements(By.XPATH,
                                                                                                '//h4[text() = \'Related Companies\']/following-sibling::div[1]//span')
                                                      if el.text != ''])
                        except:
                            related_comp = ''

                        try:
                            lead_ch = ', '.join([el.text for el in left_tags.find_elements(By.XPATH,
                                                                                           '//h4[text() = \'Lead Channel\']/following-sibling::div[1]//span')
                                                 if el.text != ''])
                            logging_string = f'{lead_ch} - {title}'
                            # self.logger.info(logging_string.replace('[^\dA-Za-z]', ''))
                        except:
                            lead_ch = ''

                        try:
                            channels = ', '.join([el.text for el in left_tags.find_elements(By.XPATH,
                                                                                            '//h4[text() = \'Channels\']/following-sibling::div[1]//span')
                                                  if el.text != ''])
                        except:
                            channels = ''

                        try:
                            keywords = ', '.join([el.text for el in left_tags.find_elements(By.XPATH,
                                                                                            '//h4[text() = \'Keywords\']/following-sibling::div[1]//span')
                                                  if el.text != ''])
                        except:
                            keywords = ''

                        try:
                            category_name = \
                                left_tags.find_element(By.CLASS_NAME, 'category--title').find_element(By.TAG_NAME,
                                                                                                      'span').get_attribute(
                                    'innerHTML').split(' |')[0]
                            category_desc = left_tags.find_element(By.CLASS_NAME, 'category--meta').get_attribute(
                                'innerHTML')
                        except:
                            category_name = ''
                            category_desc = ''

                        abstract = self._driver.find_element(By.XPATH,
                                                             "//div[contains(@class, 'article-content')]/p[@class='standfirst']").text
                        text = self._driver.find_element(By.XPATH, "//div[contains(@class, 'alt-body-copy')]").text
                        comment_count = 0
                        # comment_count = self._driver.find_element(By.ID, 'comment').find_element(By.XPATH,
                        #                                                                         './following-sibling::h4').text.split()[
                        #     1].split('(', 1)[1].split(')')[0]
                    except:
                        self.logger.exception(f'Ошибка при обработке: {article_url}')
                        self.logger.info('Закрытие вкладки и переход к след. материалу...')
                        self._driver.close()
                        self._driver.switch_to.window(self._driver.window_handles[0])
                        continue
                    else:
                        date = date.replace(tzinfo=None)
                        document = S3PDocument(
                            id=None,
                            title=title,
                            abstract=abstract,
                            text=text,
                            link=article_url,
                            storage=None,
                            other={
                                'article_type': article_type,
                                'related_comp': related_comp,
                                'lead_ch': lead_ch,
                                'channels': channels,
                                'keywords': keywords,
                                'category_name': category_name,
                                'category_desc': category_desc,
                                'tw_count': tw_count,
                                'li_count': li_count,
                                'fb_count': fb_count,
                                'comment_count': comment_count,
                            },
                            published=date,
                            loaded=None
                        )

                        try:
                            self._find(document)
                        except S3PPluginParserOutOfRestrictionException as e:
                            if e.restriction == FROM_DATE:
                                self.logger.debug(f'Document is out of date range `{self._restriction.from_date}`')
                                raise S3PPluginParserFinish(self._plugin,
                                                            f'Document is out of date range `{self._restriction.from_date}`',
                                                            e)

                    self._driver.close()
                    self._driver.switch_to.window(self._driver.window_handles[0])

                try:
                    pagination = self._driver.find_element(By.ID, 'pagination')
                    next_page_url = pagination.find_element(By.XPATH, '//*[text() = \'›\']').get_attribute('href')
                    self._driver.get(next_page_url)
                except:
                    self.logger.info('Пагинация не найдена. Прерывание обработки страницы')
                    break

            current_date = current_date - timedelta(1)
            self.logger.info(f"Изменение даты на новую: {datetime.strftime(current_date, '%Y-%m-%d')}")
