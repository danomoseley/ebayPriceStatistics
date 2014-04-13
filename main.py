from flask import Flask,render_template,request
from ebaysdk import finding, shopping
import numpy, pprint
from datetime import datetime, timedelta
import ConfigParser

config = ConfigParser.RawConfigParser()
config.read('config.cfg')
unwantedConditions = ['For parts or not working']

app = Flask(__name__)
#app.debug = True
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
	greatDeal = round(meanPrice - priceStdDev, 2)
	return render_template('statistics.html',
		earliestSoldDate=earliestSoldDate,
		latestSoldDate=latestSoldDate,
		categoryId=categoryId,
		categoryName=categoryName,
		searchTerm=searchTerm,
		sold=sold,
		unsold=unsold,
		meanPrice=meanPrice,
		priceStdDev=priceStdDev,
		greatDeal=greatDeal,
		foundConditions=foundConditions.keys())

@app.route("/findPotentialBuys/<searchTerm>/<categoryId>/<price>")
def findPotentialBuys(searchTerm, categoryId, price):
	maxEndTime = datetime.utcnow() + timedelta(minutes=15)

	print maxEndTime.isoformat()

	params = {
		'itemFilter': [
			{'name': 'EndTimeTo', 'value': maxEndTime.isoformat()},
			{'name': 'MaxPrice', 'value': str(price)},
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
			itemCondition = item['condition']['conditionDisplayName']['value']
			if itemCondition not in unwantedConditions:
				items.append(item)

		return render_template('findPotentialBuys.html',
			items=items,
			searchTerm=searchTerm,
			categoryId=categoryId,
			price=price,
			numResults=numResults)
	else:
		return render_template('noResults.html'), 204

if __name__ == "__main__":
    app.run(host='0.0.0.0')



