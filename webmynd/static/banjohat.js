var Models = {};
var Collections = {};

$(function() {
	Models.App = Backbone.Model.extend({
		url: '/app'
	});

	var AppCollection = Backbone.Collection.extend({
		url: '/app',

		/**
		 * Takes a response and extracts out the actual list of apps from it
		 *
		 * parse() is used internally in backbone, overriding it here allows it to work
		 * with our currently existing website api
		 *
		 * @param response
		 */
		parse: function(response) {
			return response.apps;
		}
	});

	var Apps = Collections.Apps = new AppCollection;
	Apps.fetch();
});