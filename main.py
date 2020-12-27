from bs4 import BeautifulSoup
import requests
import pandas as pd
import smtplib
import config
import re
import numpy as np


def is_valid_url(str):
    # Regex to check valid URL
    regex = ("((http|https)://)(www.)?" +
             "[a-zA-Z0-9@:%._\\+~#?&//=]" +
             "{2,256}\\.[a-z]" +
             "{2,6}\\b([-a-zA-Z0-9@:%" +
             "._\\+~#?&//=]*)")

    # Compile the ReGex
    p = re.compile(regex)

    # If the string is empty return false
    if str is None:
        return False

    # Return if the string matched the ReGex
    if re.search(p, str):
        return True
    else:
        return False


def get_partners_from_file():
    url_list = []
    partners_file_path = config.URL_SOURCE_FILE
    df_urls = pd.read_csv(partners_file_path, header=None)

    # validate that url is valid
    for url in df_urls.values:
        if is_valid_url(str(url)):
            url_list.append(url)
    return url_list


def get_parsed_prices():
    partners_list = get_partners_from_file()
    headers = config.USER_AGENT
    parsed_prices_dict = {}
    for url in partners_list:
        parsed_prices = []
        page = requests.get(url[0], headers=headers)
        soup = BeautifulSoup(page.content, 'html.parser')

        price = soup.find_all(['class', 'h1', 'h2', 'span', 'div', 'a', 'title', 'del', 'a', 'p'],
                              text=re.compile(r'\$'))

        dollars = []
        for x in re.findall('(\$[0-9]+(\.[0-9]+)?)', str(price)):
            dollars.append(x[0])

        price_digit = []
        for x in re.findall('([0-9]+(\.[0-9]+)?)', str(dollars)):
            price_digit.append(x[0])
        price_digit_unique = set(price_digit)

        for price in price_digit_unique:
            price = float(price)
            parsed_prices.append(price)

        parsed_prices.sort()
        parsed_prices_dict.update({str(url): parsed_prices})

    return parsed_prices_dict


def compare_prices():
    # Get current prices from file
    prices_file_path = config.PRICES_File_PATH
    df_current_prices = pd.read_csv(prices_file_path)  # header=1

    # Get parsed prices
    prices_values = list(get_parsed_prices().values())
    price_keys = list(get_parsed_prices().keys())
    df_parsed_prices = pd.DataFrame.from_dict(prices_values).transpose().fillna(0).reset_index(drop=True)
    df_parsed_prices.columns = price_keys

    # Compare current prices to parsed prices
    ne_stacked = (df_current_prices != df_parsed_prices).stack()
    for change in ne_stacked:
        if change:
            changed = ne_stacked[ne_stacked]
            changed.index.names = ['ID', 'Partner']
            difference_locations = np.where(df_current_prices != df_parsed_prices)
            changed_from = df_current_prices.values[difference_locations]
            changed_to = df_parsed_prices.values[difference_locations]

            df_price_changes = pd.DataFrame({'Current Price': changed_from, 'Parsed Price': changed_to}, index=changed.index)
            df_price_changes.to_csv('price-changes.csv', index=False, header=True, mode='w')

            alerts = []
            for row in df_price_changes.itertuples(df_price_changes.index.names):
                partner = row[0][1]
                prices = row[1:]
                msg = f'A price value on page {partner} has been changed from ${prices[0]} to ${prices[1]}'
                alerts.append(msg)
            return alerts


def send_email():
    alerts = compare_prices()
    if alerts:
        # Send email
        print('Sending email...')

        # Settings email
        email_from = config.EMAIL_FROM
        email_to = config.EMAIL_TO
        password = config.EMAIL_PASSWORD
        server = smtplib.SMTP(config.EMAIL_SERVER, config.EMAIL_PORT)

        # Create message
        msg = 'Hi Content team! \n\n' 'You are receiving this alert because the price for some of our partners has been changed.' \
              '\n\n' 'See the summary below.\n\n' + str(alerts).strip('[]').replace(', ', '\n\n').replace('"', '')

        message = '\r\n'.join([
            'From:' + email_from,
            'To:' + email_to,
            'Subject: Price Changes Alert!!!',
            msg
        ])

        server.starttls()  # security function to connect to the Gmail server (protects the email password)
        server.login(email_from, password)
        server.sendmail(email_from, [email_to], message)
        print('Email alert sent')
        server.quit()


def write_data():
    price_keys = get_parsed_prices().keys()
    price_values = get_parsed_prices().values()

    df_current_prices = pd.DataFrame.from_dict(price_values).transpose().fillna(0).reset_index(drop=True)
    df_current_prices.columns = price_keys
    df_current_prices.to_csv('current-prices.csv', index=False, header=True, mode='w')


if __name__ == '__main__':
    write_data()
    compare_prices()
    send_email()
    write_data()


'''
Phase 2 plan:
Build a cloud crawler with ScreamingFrog in Google Cloud:

1. give the specific pages on top10.com where prices needs to be updated.
2. competitors' content research - analyze content (i.e. keywords in H2, top repeated keywords) with AI, Deep Learning (PyTorch, TensorFlow bu Google)
 - discover hidden content oportinities.
3. Emails via ec2, ecs amazon service
* Automate url list to only 200, from a crawl, or internal API (Daniel Giterman)
'''
