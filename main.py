from bs4 import BeautifulSoup
import requests
import pandas as pd
import smtplib
import config
import re
import numpy as np
import pathlib


def main():
    file = pathlib.Path(config.PRICES_File_PATH)
    if not file.exists():
        write_data()
    else:
        compare_prices()
        send_email()
        write_data()


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


def get_urls_from_file():
    url_list = []
    urls_file_path = config.URL_SOURCE_FILE
    df_urls = pd.read_csv(urls_file_path, header=None)

    # validate that url is valid
    for url in df_urls.values:
        if is_valid_url(str(url)):
            url_list.append(url)
    return url_list


def get_scraped_prices():
    urls_list = get_urls_from_file()
    headers = config.USER_AGENT
    scraped_prices_dict = {}
    for url in urls_list:
        scraped_prices = []
        page = requests.get(url[0], headers=headers)
        soup = BeautifulSoup(page.content, 'html.parser')

        price = soup.find_all(['class', 'h1', 'h2', 'span', 'div', 'a', 'title', 'del', 'a', 'p'], text=re.compile(r'\$'))

        dollars = []
        for x in re.findall('(\$[0-9]+(\.[0-9]+)?)', str(price)):
            dollars.append(x[0])

        price_digit = []
        for x in re.findall('([0-9]+(\.[0-9]+)?)', str(dollars)):
            price_digit.append(x[0])
        price_digit_unique = set(price_digit)

        for price in price_digit_unique:
            price = float(price)
            scraped_prices.append(price)

        scraped_prices.sort()
        scraped_prices_dict.update({str(url): scraped_prices})

    return scraped_prices_dict


def compare_prices():
    # Get saved prices from file
    prices_file_path = config.PRICES_File_PATH
    df_saved_prices = pd.read_csv(prices_file_path)  # header=1

    # Get scraped prices
    prices_values = list(get_scraped_prices().values())
    price_keys = list(get_scraped_prices().keys())
    df_scraped_prices = pd.DataFrame.from_dict(prices_values).transpose().fillna(0).reset_index(drop=True)
    df_scraped_prices.columns = price_keys

    # Compare saved prices to scraped prices
    ne_stacked = (df_saved_prices != df_scraped_prices).stack()
    for change in ne_stacked:
        if change:
            changed = ne_stacked[ne_stacked]
            changed.index.names = ['ID', 'URL']
            difference_locations = np.where(df_saved_prices != df_scraped_prices)
            changed_from = df_saved_prices.values[difference_locations]
            changed_to = df_scraped_prices.values[difference_locations]

            df_price_changes = pd.DataFrame({'Saved Price': changed_from, 'Scraped Price': changed_to}, index=changed.index)
            df_price_changes.to_csv('price-changes.csv', index=False, header=True, mode='w')

            alerts = []
            for row in df_price_changes.itertuples(df_price_changes.index.names):
                url = row[0][1]
                prices = row[1:]
                msg = f'A price value on page {url} has been changed from ${prices[0]} to ${prices[1]}'
                alerts.append(msg)
            return alerts


def send_email():
    alerts = compare_prices()
    if alerts:
        # Send email
        print('Sending email...')

        # Get Email Settings
        email_from = config.EMAIL_FROM
        email_to = config.EMAIL_TO
        password = config.EMAIL_PASSWORD
        server = smtplib.SMTP(config.EMAIL_SERVER, config.EMAIL_PORT)

        # Create message
        msg = 'Hi Content team! \n\n' 'You are receiving this alert because the price for some of our competitors has been changed.' \
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

    else:
        print('No price changes were found')


def write_data():
    price_keys = get_scraped_prices().keys()
    price_values = get_scraped_prices().values()

    df_saved_prices = pd.DataFrame.from_dict(price_values).transpose().fillna(0).reset_index(drop=True)
    df_saved_prices.columns = price_keys
    df_saved_prices.to_csv('saved-prices.csv', index=False, header=True, mode='w')


if __name__ == '__main__':
    main()

