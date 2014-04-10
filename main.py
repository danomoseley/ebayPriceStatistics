from flask import Flask,render_template,request
from ebaysdk import finding, shopping
import numpy, pprint
import ConfigParser

config = ConfigParser.RawConfigParser()
config.read('config.cfg')

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
	if categoryId is not None:
		api.execute('findCompletedItems', {'keywords': searchTerm, 'outputSelector': 'CategoryHistogram', 'categoryId':categoryId})
	else:
		api.execute('findCompletedItems', {'keywords': searchTerm, 'outputSelector': 'CategoryHistogram'})
	response = api.response_dict()

	if type(response['categoryHistogramContainer']['categoryHistogram']) is not list:
		response['categoryHistogramContainer']['categoryHistogram'] = [response['categoryHistogramContainer']['categoryHistogram']]
		
	for category in response['categoryHistogramContainer']['categoryHistogram']:
		if (type(category['childCategoryHistogram'])) is not list:
			category['childCategoryHistogram'] = [category['childCategoryHistogram']]

	#getCategories(response['categoryHistogramContainer'])
	
	return render_template('categories.html', searchTerm=searchTerm, categories=response['categoryHistogramContainer']['categoryHistogram'])
	#for category in response['categoryHistogramContainer']['categoryHistogram']:
	#	categoryId = category['categoryId']['value']
	#	categoryName = category['categoryName']['value']
	#	return "<a href='/statistics/%s/%s'>%s</a>" % (searchTerm, categoryId, categoryName)


@app.route("/statistics/<searchTerm>/<categoryId>")
def statistics(searchTerm=None, categoryId=None):
	api.execute('findCompletedItems', {'keywords': searchTerm, 'categoryId': str(categoryId), 'itemFilter': 'SoldItemsOnly'})
	api2.execute('GetCategoryInfo', {'CategoryID': str(categoryId)})

	categoryName = api2.response_dict()['CategoryArray']['Category']['CategoryName']['value']

	sold = 0
	unsold = 0

	soldPrices = []

	for item in api.response_dict()['searchResult']['item']:
		if item['sellingStatus']['sellingState']['value'] == 'EndedWithoutSales':
			unsold += 1
		else:
			sold += 1
			soldPrices.append(float(item['sellingStatus']['currentPrice']['value']))

	meanPrice = round(numpy.mean(soldPrices), 2)
	priceStdDev = round(numpy.std(soldPrices), 2)
	greatDeal = round(meanPrice - priceStdDev, 2)
	return render_template('statistics.html', categoryName=categoryName, searchTerm=searchTerm, sold=sold, unsold=unsold, meanPrice=meanPrice, priceStdDev=priceStdDev, greatDeal=greatDeal)

if __name__ == "__main__":
    app.run(host='0.0.0.0')



