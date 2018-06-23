# -*- coding: utf-8 -*-
import os
import urllib2
import lxml.builder as lb

from bs4 import BeautifulSoup
from lxml import etree
from datetime import datetime

# USER CONFIGURATION
# Change this into your Ameblo user name
username = "ameblo-username"

base = "http://ameblo.jp/"
entries = "entrylist-%d.html"

# Change this into the WP image URL pattern for the photos that you
# have bulk-uploaded. "username", "yyyy" and "mm" need to be changed.
wp_image_url = "http://username.files.wordpress.com/yyyy/mm/%s.jpg"
wp_url = "https://username.wordpress.com"

# Change this into your Ameblo login, name and e-mail
authorLogin = 'ameblo-username'
authorName = u'author name'
authorEmail = 'author-email@example.com'

# START OF CODE
categories = set()
articles = []

class Comment:
    id = 100

    def __init__(self, author, content, dt):
        self.id = Comment.id
        self.author = author
        self.content = content
        self.dt = dt
        self.author_url = None

        Comment.id = Comment.id + 1

    def __unicode__(self):
        return u"Comment by %s (%s) on %s" % (self.author, self.author_url, self.dt)

    def __str__(self):
        return unicode(self).encode('utf-8')

class Article:
    def __init__(self, title):
        self.title = title
        self.content = None
        self.dt = datetime.now()
        self.category = None
        self.comments = []

    def addComment(self, c):
        author_element = c.find(class_='commentAuthor')
        author = author_element.string

        content = c.find('div', class_='commentBody')

        dt = c.find('span', class_='commentTime').find('time').string
        dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')

        comment = Comment(author, content, dt)
        if 'ownerComment' in c['class']:
            comment.author_url = wp_url
        elif author_element.name == 'a':
            comment.author_url = author_element['href']

        self.comments.append(comment)

def addArticle(title, url):
    page = urllib2.urlopen(url)
    soup = BeautifulSoup(page, 'lxml')
    article = soup.find('article')
    aside = soup.find('aside')

    if article:
        a = Article(title)

        # Setting date
        dt = article.find('span', class_='articleTime').find('time').string
        a.dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')

        # Setting category
        category = article.find('span', class_='articleTheme').find('a')
        if category:
            a.category = category.string
            categories.add(a.category)

        # Fetch content
        a.content = article.find('div', class_='articleText')

        # Go through images in content
        for e in a.content.find_all('a', class_='detailOn'):
            eid = e['id']
            img = e.find('img')

            # If image has not been downloaded yet, fetch it
            targetFile = eid + '.jpg'
            if not os.path.exists(targetFile):
                target = open(targetFile, 'w')
                target.write(urllib2.urlopen(img['src']).read())
                target.close()

            # Replace image source with WP URL
            img['src'] = wp_image_url % eid
            e.replace_with(img)

        # Collect comments
        if aside:
            comments = aside.find('ul', class_='commentList')

            if comments:
                for c in comments.find_all('div', class_='blogComment'):
                    a.addComment(c)

        articles.append(a)

# MAIN CODE
print "Scraping articles from %s%s" % (base, username)
x = 1
doLoop = True
while doLoop:
    url = base + username + "/" + entries % x
    print "Fetching URL: " + url

    page = urllib2.urlopen(url).read()
    soup = BeautifulSoup(page, 'lxml')

    for link in soup.select('div.contentTitleArea a.contentTitle'):
        addArticle(link.string, link['href'])

    # Check for presence of the Next button
    doLoop = len(soup.select('a.pagingNext'))
    x += 1

print "\n-------------------------------"
print "%d articles\n%d categories" % (len(articles), len(categories))
print "-------------------------------\n"

# GENERATING WORDPRESS WXR/XML FILE
NS_CONTENT = 'http://purl.org/rss/1.0/modules/content/'
NS_DC = 'http://purl.org/dc/elements/1.1/'
NS_WP = 'http://wordpress.org/export/1.2/'

E = lb.ElementMaker(nsmap={
        'content': NS_CONTENT,
        'dc': NS_DC,
        'wp': NS_WP
    })

nsContent = lb.ElementMaker(namespace=NS_CONTENT)
nsDc = lb.ElementMaker(namespace=NS_DC)
nsWp = lb.ElementMaker(namespace=NS_WP)

rss = E.rss(
        E.channel(
            E.title("Blog title"),      # Probably optional
            E.link("http://blog.url"),  # Probably optional
            E.language("ja-JP"),        # Probably optional
            nsWp.wxr_version("1.2")     # Required
            )
        )

# Author element
displayName = nsWp.author_display_name()
displayName.text = etree.CDATA(authorName)

author = nsWp.author(
        nsWp.author_login(authorLogin),
        displayName,
        nsWp.author_email(authorEmail)
        )

rss.find('channel').append(author)

# Add category elements
for category in categories:
    nicename = nsWp.category_nicename(category)

    cat_name = nsWp.cat_name()
    cat_name.text = etree.CDATA(category)
    rss.find('channel').append(nsWp.category(nicename, cat_name))

# Add article items
for article in articles:
    creator = nsDc.creator()
    creator.text = etree.CDATA(authorLogin)

    content = nsContent.encoded()
    content.text = etree.CDATA(article.content.decode_contents())

    item = E.item(
            E.title(article.title),
            creator,
            content,
            nsWp.post_date(article.dt.strftime("%Y-%m-%d %H:%M:%S")),
            nsWp.post_name(article.title),
            nsWp.status("publish"),
            nsWp.post_type("post")
            )

    if article.category:
        category = E.category(domain="category", nicename=article.category)
        category.text = etree.CDATA(article.category)
        item.append(category)

    if len(article.comments):
        for c in article.comments:
            content = nsWp.comment_content()
            content.text = etree.CDATA(c.content.decode_contents())

            author = nsWp.comment_author()
            author.text = etree.CDATA(c.author)

            comment = nsWp.comment(
                    nsWp.comment_id(str(c.id)),
                    author,
                    nsWp.comment_date(c.dt.strftime("%Y-%m-%d %H:%M:%S")),
                    content,
                    nsWp.comment_approved("1")
                    )

            if c.author_url:
                comment.append(nsWp.comment_author_url(c.author_url))

            item.append(comment)

    rss.find('channel').append(item)

# Write to XML file
output = open(username + ".xml", "w")
output.write('<?xml version="1.0" encoding="UTF-8" ?>\n')
output.write(etree.tostring(rss, pretty_print=True, encoding="utf-8"))
output.close()
