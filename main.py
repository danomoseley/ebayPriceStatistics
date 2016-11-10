from flask import Flask,render_template,request
from ebaysdk import finding, shopping
import numpy, pprint
from datetime import datetime, timedelta
import ConfigParser
import os

DIR = os.path.dirname(os.path.realpath(__file__))

config = ConfigParser.RawConfigParser()
config.read(os.path.join(DIR,'config.cfg'))
unwantedConditions = ['For parts or not working']

app = Flask(__name__)
app.debug = True
appid = config.get('Ebay','appid')
api = finding(appid=appid)
api2 = shopping(appid=appid)

@app.route('/')
def index():
	return render_template('index.html')

@app.route('/findCategory', methods = ['POST'])
@app.route('/findCategory/<searchTerm>')
@app.route('/findCategory/<searchTerm>/<categoryId>')
def findCategory(searchTerm=None, categoryId=None):
	if searchTerm is None:
		searchTerm = request.form['searchTerm']
	params = {
		'itemFilter': [
	        {'name': 'Condition', 'value': 'Used'},
	        #{'name': 'SoldItemsOnly', 'value': True}
	    ],
		'sortOrder': 'EndTimeSoonest',
		'keywords': searchTerm,
		'outputSelector': 'CategoryHistogram'
	}
	if categoryId is not None:
		params['categoryId'] = categoryId

	api.execute('findCompletedItems', params)
	response = api.response_dict()

	if type(response['categoryHistogramContainer']['categoryHistogram']) is not list:
		response['categoryHistogramContainer']['categoryHistogram'] = [response['categoryHistogramContainer']['categoryHistogram']]
		
	for category in response['categoryHistogramContainer']['categoryHistogram']:
		if (type(category['childCategoryHistogram'])) is not list:
			category['childCategoryHistogram'] = [category['childCategoryHistogram']]

	return render_template('categories.html', searchTerm=searchTerm, categories=response['categoryHistogramContainer']['categoryHistogram'])

@app.route("/statistics/<searchTerm>/<categoryId>")
def statistics(searchTerm=None, categoryId=None):
	stats = getStats(searchTerm, categoryId)

	return render_template('statistics.html',
		stats=stats,
		categoryId=categoryId,
		searchTerm=searchTerm)

def getStats(searchTerm=None, categoryId=None):
	api2.execute('GetCategoryInfo', {'CategoryID': str(categoryId)})

	categoryName = api2.response_dict()['CategoryArray']['Category']['CategoryName']['value']

	sold = 0
	unsold = 0

	soldPrices = []

	earliestSoldDate = None
	latestSoldDate = None
	currentPage = 0
	totalPages = 1
	while currentPage < 10 and currentPage < totalPages:
		api.execute('findCompletedItems', {
			'itemFilter': [
		        {'name': 'Condition', 'value': 'Used'},
		        #{'name': 'SoldItemsOnly', 'value': True}
		    ],
			'paginationInput.pageNumber': currentPage,
			'sortOrder': 'EndTimeSoonest',
			'keywords': searchTerm,
			'categoryId': str(categoryId),
		})
		response = api.response_dict()

		totalPages = int(response['paginationOutput']['totalPages']['value'])

		foundConditions = {}

		if type(response['searchResult']['item']) is not list:
			response['searchResult']['item'] = [response['searchResult']['item']]

		for item in response['searchResult']['item']:
			itemCondition = item['condition']['conditionDisplayName']['value']
			if itemCondition not in unwantedConditions:
				foundConditions[itemCondition] = True
				if item['sellingStatus']['sellingState']['value'] == 'EndedWithoutSales':
					unsold += 1
				else:
					soldPrices.append(float(item['sellingStatus']['currentPrice']['value']))
					if sold == 0:
						latestSoldDate = item['listingInfo']['endTime']['value']
					else:
						earliestSoldDate = item['listingInfo']['endTime']['value']
					sold += 1
		currentPage += 1

	meanPrice = round(numpy.mean(soldPrices), 2)
	priceStdDev = round(numpy.std(soldPrices), 2)
	goodDeal = round(meanPrice - (priceStdDev/2), 2)

	autoGoodDealMargin = config.get('Ebay','auto_good_deal_margin')
	if autoGoodDealMargin is not None:
		if goodDeal < (meanPrice - int(autoGoodDealMargin)):
			goodDeal = meanPrice - int(autoGoodDealMargin)

	return {
		'mean_price': round(meanPrice, 2),
		'price_std_dev': round(priceStdDev, 2),
		'good_deal': round(goodDeal, 2),
		'found_conditions': foundConditions.keys(),
		'earliest_sold_date': earliestSoldDate,
		'latest_sold_date': latestSoldDate,
		'category_name': categoryName,
		'sold': sold,
		'unsold': unsold
	}

@app.route("/findPotentialBuys/<searchTerm>/<categoryId>")
def findPotentialBuys(searchTerm, categoryId):
	add_minutes = config.get('Ebay','potential_buys_minutes')
	maxEndTime = datetime.utcnow() + timedelta(minutes=int(add_minutes))
	stats = getStats(searchTerm, categoryId)

	params = {
		'itemFilter': [
			{'name': 'EndTimeTo', 'value': maxEndTime.isoformat()},
			{'name': 'MaxPrice', 'value': str(stats['good_deal'])},
		],
		'sortOrder': 'EndTimeSoonest',
		'keywords': searchTerm
	}
	if categoryId is not None:
		params['categoryId'] = categoryId

	api.execute('findItemsAdvanced', params)
	response = api.response_dict()

	if 'item' in response['searchResult']:
		numResults = len(response['searchResult']['item'])

		if type(response['searchResult']['item']) is not list:
			response['searchResult']['item'] = [response['searchResult']['item']]

		items = []

		for item in response['searchResult']['item']:
			itemId = item['itemId']['value']

			itemCondition = item['condition']['conditionDisplayName']['value']
			if itemCondition not in unwantedConditions:
				params = {
					'ItemID':itemId,
					'DestinationPostalCode': config.get('Ebay','shipping_zip_code')
				}
				api2.execute('GetShippingCosts', params)
				shippingCostResponse = api2.response_dict()

				shippingCost = shippingCostResponse['ShippingCostSummary']['ShippingServiceCost']['value']
				currentPrice = item['sellingStatus']['currentPrice']['value']

				if float(currentPrice) < float(stats['good_deal']):
					items.append(item)

		if not items:
			return render_template('noResults.html'), 204
		else:
			return render_template('findPotentialBuys.html',
				items=items,
				searchTerm=searchTerm,
				categoryId=categoryId,
                stats=stats,
				numResults=numResults,
                add_minutes=add_minutes)
	else:
		return render_template('noResults.html'), 204

if __name__ == "__main__":
    app.run(host='0.0.0.0')



