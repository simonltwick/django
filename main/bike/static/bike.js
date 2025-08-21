// javascript for bike website

function change_link_visibility(id) {
	/* switch visibility for row#id:
	find tr#link_id>td.link-link, add class hidden
	find tr#link_id>td.link-form, remove class hidden */
	// row = $('tr#link_' + id).get();
	link = $('tr#link_' + id).find('td.link-link').addClass('hidden');
	form = $('tr#link_' + id).find('td.link-form').removeClass('hidden');
}

function mark_link_deleted(id) {
	/* toggle: mark form deleted and set strikethrough */

	// <input> for deleted has id id_links-0-DELETE vs passed id=id_links-0-id
	delete_id = id.slice(0, -3) + "-DELETE";
	deleted_old = $('#' + delete_id).prop("checked");
	deleted = !deleted_old;
	console.info("link", id, "deleted_old=", deleted_old, "deleted =", deleted);
	$('#' + delete_id).prop("checked", deleted);
	
	// find the link itself and set strikethrough
	link = $('tr#link_' + id).find('a')[0];
	link.style.textDecoration = deleted ? "line-through": "underline";
	console.info("results: input.checked=", $('#' + delete_id).prop("checked"),
		"link.style.textDecoration=", link.style.textDecoration);
}

function displayMessage(message, msgClass) {
	/* display a message in the message area.  msg_class, if provided,
	is a bootstrap class such as text-info/warning/error/success */
	let html = "<li";
	if (msgClass) {
		html += ' class="' + msgClass + '"';
	}
	html += ">" + message + "</li>";
	// console.info("displayMessage(", message, ") -> html: ", html);
	$("#messages").html(html);
	showMessages();
}

function showMessages() {
	/* show pre-set messages 
	If the header is not shown, we have to show it or messages are invisible
	*/
	let element = document.getElementById("messages");
	let baseHeaderElement = document.getElementById("base-header")
	let navIsHidden = baseHeaderElement.classList.contains("d-none");
	if (navIsHidden) {
		baseHeaderElement.classList.remove("d-none");
	}
	element.classList.remove("d-none") ;

	setTimeout(function() {
		element.classList.add("d-none");
		if (navIsHidden) {
			baseHeaderElement.classList.add("d-none");
		}
	}, 3500);
}
