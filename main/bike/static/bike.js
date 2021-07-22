// javascript for bike website

function change_link_visibility(id) {
	/* switch visibility for row#id:
	find tr#link_id>td.link-link, add class hidden
	find tr#link_id>td.link-form, remove class hidden */
	// row = $('tr#link_' + id).get();
	link = $('tr#link_' + id).find('td.link-link').addClass('hidden');
	form = $('tr#link_' + id).find('td.link-form').removeClass('hidden');
}