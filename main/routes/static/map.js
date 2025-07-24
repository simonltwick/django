let popup;  		//displayed popup
let popMarker;		//marker of last popup
let popLocation;	//location of last popup

let dragStartLatLng;  // start of drag action for place

let nearbyTracksUrl;  // url for searching tracks

let preference;  // nearby search preference


/* ------ initialisation ------ */

// make the osm layer
const hrefOsm = "https://www.openstreetmap.org/copyright";
const attrOsm = `© <a href='${hrefOsm}'>OpenStreetMap</a>`;
const tilesOsm = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const layerOsm = L.tileLayer(tilesOsm, { attribution: attrOsm });

const linkOsm = '<a href="http://openstreetmap.org">OpenStreetMap</a>';

// OpenCycleMap layer - requires an API key from thunderforest.com
const ocmApiKey = JSON.parse(document.getElementById('ocmApiKey').textContent);
const hrefOcm = '<a href="http://thunderforest.com/">Thunderforest</a>';
const attrOcm = '&copy; ' + linkOsm + ' Contributors & ' + hrefOcm;
const tilesOcm = 'http://{s}.tile.thunderforest.com/cycle/{z}/{x}/{y}.png?apikey='
	+ ocmApiKey;
const layerOcm = L.tileLayer(tilesOcm, { attribution: attrOcm, maxZoom: 18 });

// Google Maps / Google Satellite maps
const googleMapsUrl = 'http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}';
const googleSatMapUrl = 'http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}';
// terrain, traffic, biking overlays also available
const layerGoogle = L.tileLayer(googleMapsUrl, {
	maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
});
const layerGoogleSat = L.tileLayer(googleSatMapUrl, {
	maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
});

// Others copied from example using the folium package at
// https://towardsdatascience.com/build-interactive-gps-activity-maps-from-gpx-files-using-folium-cf9eebba1fe7

// national geographic
const natGeoUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}';
const natGeoAttr = 'Tiles &copy; Esri &mdash; National Geographic, Esri, DeLorme, NAVTEQ, UNEP-WCMC, USGS, NASA, ESA, METI, NRCAN, GEBCO, NOAA, iPC';
const layerNatGeo = L.tileLayer(natGeoUrl, natGeoAttr);

// terrain map
const terrainUrl = 'http://tile.stamen.com/terrain/{z}/{x}/{y}.jpg';
const layerTerrain = L.tileLayer(terrainUrl, attr = 'terrain-bcg');


const map = L.map("map", { layers: [layerOsm] })
	// allow user to click anywhere & show popup with lat/lon
	.on('click', onMapClick);

try {
	const initBounds = JSON.parse(document.getElementById('initBounds').textContent);
	console.info("initBounds=", initBounds);
	map.fitBounds(initBounds);
} catch {
	map.fitWorld();
}


// map controls - scale, overlays
L.control.scale({ position: "bottomright" }).addTo(map);

const baseLayers = {
	OpenStreetMap: layerOsm,
	OpenCycleMap: layerOcm,
	Google: layerGoogle,
	GoogleSatellite: layerGoogleSat,
	Terrain: layerTerrain,
	NatGeographic: layerNatGeo,
};

const overlays = {};
const layerControl = L.control.layers(
	baseLayers, overlays, { position: "bottomleft" }
).addTo(map);

class NavControl extends L.Control {
	constructor (options) {
		super(options);
		this.container = document.createElement("div");
		this.container.classList.add("leaflet-control");
		this.container.classList.add("nav-control");
	}
	onAdd(map) {
		document.getElementById("base-header").classList.toggle("d-none")
		this.container.innerHTML = `<span class='oi oi-menu'
			data-toggle='tooltip' title='Show/hide Menu'></span>`;
		// connect event listeners
		this.container.addEventListener("click", this.onClick)
		return this.container;
	}
	onClick(event) {
		// toggle the navbar visibility
		L.DomEvent.stopPropagation(event);
		document.getElementById("base-header").classList.toggle("d-none")
	}
}

const navControl = new NavControl({position: "topright"}).addTo(map);

const trackStyle = {color: '#ff00ff',
    weight: 3,
    opacity: 0.5
};

// add layers for tracks & places

let placeIcons;
let placesLayer = L.geoJSON().addTo(map);   // map layer for places
layerControl.addOverlay(placesLayer, "Places");
let tracksLayer = L.geoJSON().addTo(map); 
layerControl.addOverlay(tracksLayer, "Tracks");
let tracksHidden = [];


// show initial tracks, or if none, show welcome dialog
let dialog = document.getElementById("map-dialog");
const initialTracks = JSON.parse(document.getElementById('initialTracks'
	).textContent);

if (initialTracks) {
	showTracks(initialTracks);
} else {
	/* show map dialog, pre-populated with a help/info message */
	dialog.showModal();
}

// init preferences & place icons
// get preference & buildPlaceIcons cannot be run in parallel
$.get("/routes/api/preference", "json", function(data){
	json_data = JSON.parse(data);
	updatePreference(json_data);
	buildPlaceIcons();
});

function buildPlaceIcons() {
	$.get('/routes/api/place/types/icons', null, buildPlaceIconDict, 'json');
	// nb. placeIcons is not initialised until response received
}

function buildPlaceIconDict(data) {
	refreshPlaceIconDict(data);
	// console.info("buildPlaceIconDict:", data, placeIcons);
}


/* ----- end of initialisation ------ */

function setMapBounds() {
	// resize the map to fit placesBounds and tracksBounds
	let trackBounds = tracksLayer ? tracksLayer.getBounds(): null;
	let placesBounds = placesLayer ? placesLayer.getBounds(): null;
	let combinedBounds = (trackBounds? (
		placesBounds? placesBounds.extend(trackBounds) : trackBounds
		) : placesBounds); 
	if (combinedBounds) {
		map.fitBounds(combinedBounds);
	} else {
		console.error("map bounds not defined:", trackBounds, placesBounds);
	}
}


// create popup when user clicks on map
const mapClickPopupContent = `</p>
	<a class="btn" onClick="onRoutesSearch()">
	  <span class="oi oi-magnifying-glass" data-toggle="tooltip" title="Search"
	  />
	</a>
	<button type="button" class="btn btn-outline-secondary"
	  onClick="createPlace()">
	  New Place</button>
	<a class="btn" onClick="onPreference()">
	  <span class="oi oi-cog" data-toggle="tooltip" title="Preference"/>
	</a>`
// these buttons shown when no tracks are visible on the map
const nearbyButtons1Html = `<p>
	<button class="btn btn-outline-secondary" onClick="nearbyTracks()">
	  Nearby Tracks</button>
	<button class="btn btn-outline-secondary" onClick="nearbyPlaces()">
	  Nearby Places</button>
	</p>`;
// these buttons shown if tracks are already visible on the map
const nearbyButtons2Html = `<p>
	<div class="btn-group" role="group">
	<button onClick="nearbyTracks()" class="btn btn-outline-secondary">
	  Nearby Tracks</button>
	  <button type="button" 
	    class="btn btn-outline-secondary dropdown-toggle"
		data-toggle="dropdown" aria-expanded="false" aria-haspopup="true"
		id="nearby-tracks1">
	    <!-- <span class="invisible">Toggle Dropdown</span> -->
	  </button>
	  <div class="dropdown-menu" aria-labelledby="nearby-tracks1">
	    <a href="#" class="btn btn-outline-secondary dropdown-item"
			onClick="nearbyTracks('add')">
		  	Add to tracks already displayed</a>
	    <a href="#" class="btn btn-outline-secondary dropdown-item" 
			onClick="nearbyTracks('reduce')">
		  	Search only tracks already displayed</button></a>
	  </div>
	</div>
	<button class="btn btn-outline-secondary" onClick="nearbyPlaces()">Nearby Places</button>
	</p>`;

function onMapClick(event) {
	popLocation = event.latlng;
	let buttonsHtml = ((tracksLayer && map.hasLayer(tracksLayer)) ?
					   nearbyButtons2Html : nearbyButtons1Html);
	popup = L.popup()
		.setLatLng(popLocation)
		.setContent(
			'<p>You clicked at ' + popLocation.toString()
			+ mapClickPopupContent
			+ buttonsHtml)
		.openOn(map);
	// TODO: if tracks layer is not shown, don't show additional track options      
}

function replaceMapOverlay(oldOverlay, newOverlay, overlayName) {
	if (oldOverlay) {
		map.removeLayer(oldOverlay);
		layerControl.removeLayer(oldOverlay);
	}
	map.addLayer(newOverlay);
	layerControl.addOverlay(newOverlay, overlayName);
	return newOverlay;
}


function onRoutesSearch() {
	// search tracks or places from a form.
	getMapDialogData("/routes/api/search/");
	popup.close();
}

function onSearchFormSubmit(event) {
	event.preventDefault();
	searchType = document.getElementById("tracks-search"
		).classList.contains("active") ? 'track': 'place'
	requestUrl = '/routes/api/search/?search_type=' + searchType;
	$.post(requestUrl, $('#searchForm').serialize(), searchResults, null
		).fail(requestFailMsg); 
	/* this automatically parses result data to json or html/text */
}

function searchResults(data) {
	// handle search results, which could be html if form errors, or json
	if (!data.status) { // ParseError: html was returned
		showMapDialog(data);
		return;
	}
	// json data was returned, so display it
	onCloseMapDialog();
	if (data.hasOwnProperty("tracks"))  {
		console.info("searchResults: showing", data.tracks.features.length, "tracks");
		showTracks(data["tracks"]);
	} else if (data.hasOwnProperty("places")) {
		console.info("searchResults: showing", data.places.features.length, "places");
		showPlaces(data["places"]);
	} else {
		console.info("Unrecognised search results:", data);
		alert("Unrecognised response to search request");
	}
}

// error handling
function requestFailMsg(jqXHR, textStatus, errorThrown) {
	console.error("Request failed:",
		{jqHXR: jqXHR, textStatus: textStatus, errorThrown: errorThrown});
	let msg = jqXHR;
	if (jqXHR.status) {
		msg = "Status code " + jqXHR.status + ": " + jqXHR.statusText;
	}
	msg = "Server request " + requestUrl + " returned " + msg;
	window.alert(msg + ': ' + textStatus);
	// log_error(msg, errMsg);
}

function ajaxFail(jqXHR, textStatus, errorThrown) {
	// translate to a requestFailMsg call
	requestFailMsg({ "status": textStatus, "statusText": errorThrown });
}

function log_error(msg) {
	alert(msg);
}

/*
 ------ Track handling ------
 */
function nearbyTracks(searchType) {
	/* get tracks nearby popLocation.   depending on the value of searchType,
	add to tracks already shown, replace tracks already shown, or limit the
	search to those already shown.  This is done by resubmitting the 
	query with the combined search term */
	switch (searchType){
		case undefined:
			nearbyTracksUrl = (
				'/routes/api/track?latlon=' + popLocation.lat + ',' + popLocation.lng);
		    break;
		case "add":
			nearbyTracksUrl += (
				"&orlatlon=" + popLocation.lat + ',' + popLocation.lng);
			break;
		case "reduce":
			nearbyTracksUrl += (
				"&andlatlon=" + popLocation.lat + ',' + popLocation.lng);
			break;
		default:
			log_error("nearbyTracks: unexpected value for searchType: "
					  + searchType);
		};
	// console.info("nearbyTracks: settings=", settings, ", nearbyTracksUrl=", nearbyTracksUrl);
	$.get(nearbyTracksUrl, null, showTracks, 'json').fail(
		function(_, status, jqXHR){
			log_error("nearbyTracks request status=" + status +
				', response=' + jqXHR);
			console.error('jqXHR=', jqXHR);
		});
	map.closePopup();
	// add search area to map
	tracksLayer.clearLayers();
	// console.info("nearbyTracks: preference=", preference);
	L.circle(popLocation, {
			radius: preference.track_nearby_search_distance_metres,
			color: "blue",
			weight: 1,
			opacity: 0.5,
			fill: false}).addTo(tracksLayer);
}

function showTracks(trackList) {
	// add tracks to the map
	if (trackList.length < 1) {
		alert("No matching tracks found");
		return
	}
	// console.info('showTracks(): trackList=', trackList)
	const oldTracksLayer = tracksLayer;
	tracksLayer = L.geoJSON(trackList, {
		style: trackStyle,
		onEachFeature: onTrackShow
	});
	// copy the search circle to the new tracksLayer
	oldTracksLayer.eachLayer((layer) => tracksLayer.addLayer(layer));
	tracksHidden = [];
	// showSidebarSection(true, 'track');
	tracksLayer = replaceMapOverlay(oldTracksLayer, tracksLayer, "Tracks");
	tracksBounds = tracksLayer.getBounds();
	setMapBounds();
}

function onTrackShow(feature, layer) {
	/*if (feature.geometry && feature.geometry.type
			&& feature.geometry.type == "MultiLineString") {
		addTrackStartStopMarkers(feature, layer);
	} */
	
	layer.on({
		click: onTrackClick,
		mouseover: onTrackMouseOver,
		mouseout: onTrackMouseLeave,
		});
	// addToTrackSidebar(feature, layer);
}

function trackHide(marker) {
	if (!marker) {
		marker = popMarker;
	}
	// only tracks have marker.feature.properties (search circle doesn't)
	if (!(marker.feature && marker.feature.properties)) {
		return;
	}
	//tracksGeoLayer.remove(marker);  // removes the whole tracksGeoLayer
	marker.removeFrom(tracksLayer);
	tracksHidden.push(marker);
	if (marker.feature.properties.startStopMarkers) {
		for (const startStopMarker
				of marker.feature.properties.startStopMarkers) {
			startStopMarker[0].removeFrom(tracksOverlay);
			startStopMarker[1].removeFrom(tracksOverlay);
		}
	}
	popMarker.closePopup();
}

function trackHideOthers() {
	tracksLayer.eachLayer(function(marker) {
		if (marker !== popMarker) {
			trackHide(marker)
		}
	});
	popMarker.closePopup();
}

function tracksUnhide() {
	/* unhide any hidden tracks */
	tracksHidden.forEach(trackUnhide);
	tracksHidden = [];
}

function trackUnhide(marker) {
	/* unhide a track by adding back to TracksGeoLayer */
	tracksLayer.addLayer(marker);
	// addTrackStartStopMarkers(marker.feature, marker);
}

function onTrackMouseOver(ev) {
	layerChangeState(ev.target, 'track', true, null);
	const trackID = ev.target.feature.properties.id;
	$("#track-sidebar-item-"+trackID).addClass("highlight");
}

function onTrackMouseLeave(ev) {
	const trackID = ev.target.feature.properties.id;
	$("#track-sidebar-item-" + trackID).removeClass("highlight");
	layerChangeState(ev.target, 'track', false, null);
}

const trackPopupContent = `<h4>{{name}}</h4>
<div class="spinner-border text-secondary" role="status">
  <span class="invisible">Loading tags...</span>
</div>`;

function onTrackClick(event) {
	L.DomEvent.stopPropagation(event);
	popMarker = event.target;
	popLocation = event.latlng;
	let pk = popMarker.feature.properties.pk;
	if (!pk) {
		showPopup("<h4>"+ popMarker.feature.properties.name + `</h4>
			<p>GPX for view only - no details stored in the database</p>`);
		return;
	}
	requestUrl = '/routes/track/' + pk;
	// temp content while waiting for response
	const popupContent = trackPopupContent
		.replaceAll('\{\{name\}\}', popMarker.feature.properties.name);
	showPopup(popupContent);
	$.get(requestUrl, null, showPopup, 'html')
		.fail(requestFailMsg);
}

function trackDetails() {
	requestUrl = '/routes/track/' + popMarker.feature.properties.pk + '?detail=True';
	$.get(requestUrl, null, showPopup, "html")
		.fail(requestFailMsg);
}

function onTrackDetailSubmit(event) {
	event.preventDefault();
	let formData = new FormData(event.target);
	let pk = formData.get("pk");
	let requestUrl = "/routes/track/" + (pk ? pk: "")
	$.ajax({
		url: requestUrl,
		method: "POST",
		data: formData,
		processData: false,
	    contentType: false,
		dataType: "html",
		success: function(data) {
			if (data){showPopup(data);
			} else {
				popup.close();
			}
		},
		error: requestFailMsg
	});
}

/*
// ------ place handling ------
*/
function nearbyPlaces(searchType) {
	/* get places nearby popLocation.   depending on the value of searchType,
	add to places already shown, replace places already shown, or limit the
	search to those already shown.  This is done by resubmitting the 
	query with the combined search term */
	switch (searchType){
		case undefined:
			nearbyPlacesUrl = (
				'/routes/api/place?latlon=' + popLocation.lat + ',' + popLocation.lng);
		    break;
		case "add":
			nearbyPlacesUrl += (
				"&orlatlon=" + popLocation.lat + ',' + popLocation.lng);
			break;
		case "reduce":
			nearbyPlacesUrl += (
				"&andlatlon=" + popLocation.lat + ',' + popLocation.lng);
			break;
		default:
			log_error("nearbyPlaces: unexpected value for searchType: "
					  + searchType);
		};
	// console.info("nearbyPlaces: settings=", settings, ", nearbyPlacesUrl=", nearbyPlacesUrl);
	$.get(nearbyPlacesUrl, null, showPlaces, 'json').fail(
		function(_, status, jqXHR){
			log_error("nearbyPlaces request status=" + status +
				', response=' + jqXHR);
			console.error('jqXHR=', jqXHR);
		});
	map.closePopup();
	// add search area to map
	if (placesLayer) {placesLayer.clearLayers();}
	// console.info("nearbyPlaces: preference=", preference);
	L.circle(popLocation, {
			radius: preference.place_nearby_search_distance_metres,
			color: "blue",
			weight: 1,
			opacity: 0.5,
			fill: false}).addTo(placesLayer);
}

function showPlaces(data) {
	const oldPlacesLayer = placesLayer;
	placesLayer = L.geoJSON(data, {
		pointToLayer: getPlaceMarker,
		onEachFeature: onPlaceShow
	});
	// copy the search circle to the new placesLayer
	oldPlacesLayer.eachLayer((layer) => placesLayer.addLayer(layer));
	// showSidebarSection(true, 'place');
	placesLayer = replaceMapOverlay(oldPlacesLayer, placesLayer, "Places");
	placesBounds = placesLayer.getBounds();
	setMapBounds();
}

function createPlace() {
	// handle 'new place' 
	requestUrl = "/routes/place";
	$.get(requestUrl, null, showPopup, 'html')
		.fail(requestFailMsg);
}

function onPlaceFormSubmit(event) {
	// submit the place form using html/post
	// expects a json response if all ok
	// if form errors, an html response is received, which triggers error
	// handling
	event.preventDefault();

	// fill in hidden values in form for position
	document.getElementById("place-lat").value = popLocation.lat;
	document.getElementById("place-lon").value = popLocation.lng;
	let formData = new FormData(event.target);
	let pk = formData.get("pk")
	let requestUrl = "/routes/place/" + (pk ? pk: "")
	
	$.ajax({
		url: requestUrl,
		method: 'POST',
		data: formData,
		processData: false,
		contentType: false,
		dataType: "json",  // if not json, error will be called
		success: formData.get("pk") ? placeUpdateOK : placeInsertOK,
		error: function(jqXHR, textStatus, errorThrown) {
			alert('Your request was not sent successfully.');
			console.error(errorThrown);
		}
	});
}

function placeUpdateOK(data) {
	/* replace the existing marker & close the popup. */
	popMarker.removeFrom(placesLayer);
	placeInsertOK(data);
	return;
}

function placeInsertOK(data) {
	/* add a new marker for the new place 
	   data = name, pk, type */
	const fakeFeature = { properties: data };
	let placeMarker = getPlaceMarker(fakeFeature, popLocation)
		.on("click", onPlaceClick);
	//console.info("placeInsertOK(data=", data, "): feature=", fakeFeature,
	//			 ", latlon=", popLocation, " -> marker=", placeMarker);
	placesLayer.addLayer(placeMarker);
	popup.remove();
}


function refreshPlaceIconDict(data) {
	const placeIconSize = [16, 16];  // should match css .place-icon
	placeIcons = {};
	for (const [key, value] of Object.entries(data)) {
		placeIcons[key] = L.icon({
			iconUrl: value.icon,
			iconSize: placeIconSize,
			placeTypeName: value.name
		});
	}
}

function getPlaceMarker(feature, latlng) {
	/* return a marker depending on the type of the feature */
	if (!feature.properties){ throw "undefined feature.properties";}
	let placeType = feature.properties.type;
	let sel_icon = placeIcons[placeType];
	if (!sel_icon) throw "undefined sel_icon for placeType="+placeType;
	let marker = L.marker(latlng, {
		icon: sel_icon,
		draggable: true,
		placeID: feature.properties.pk,
		placeName: feature.properties.name,
		placeType: placeType  // pk of placeType
	})
		.on('dragstart', placeDragStart)
		.on('dragend', placeDragEnd);
	// console.info("getPlaceMarker", feature.properties, sel_icon, marker.options);
	return marker;
}

function placeDragStart(event) {
	dragStartLatLng = event.target.getLatLng();
}

function placeDragEnd(event) {
	popMarker = event.target;
	requestUrl = "/routes/place/" + popMarker.options.placeID + "/move"
	$.ajax({
		url: requestUrl,
		method: "GET",
		dataType: "html",
		success: function(content){
			// open a popup to confirm the move
			popup = L.popup().setContent(content);
				popMarker.bindPopup(popup)
					.openPopup();
		},
		error: function() {
			onPlaceMoveUndo();
			requestFailMsg();
		}
	});
}

function onPlaceMoveConfirm(event) {
	event.preventDefault();
	newPos = popMarker.getLatLng();
	document.getElementById("place-move-lat").value = newPos.lat;
	document.getElementById("place-move-lon").value = newPos.lng;
	let formData = new FormData(event.target);
	let pk = formData.get("pk")
	requestUrl = "/routes/place/" + pk + "/move"
		
	$.ajax({
		url: requestUrl,
		method: 'POST',
		data: formData,
		processData: false,
		contentType: false,
		success: null,
		error: requestFailMsg
	});
	if (popup) {popup.remove();}
}

function onPlaceMoveUndo() {
	// move back to original place (also called from place_move form)
	console.info("move cancelled.");
	if (popup) {popup.remove();}
	popMarker.setLatLng(dragStartLatLng);
}

function onPlaceShow(feature, layer) {
	layer.on({
		click: onPlaceClick,
		mouseover: onPlaceMouseOver,
		mouseout: onPlaceMouseLeave
	});
	// addToPlaceSidebar(feature, layer);
}

const placePopupContent = `<p>{{name}}</p><p>{{type}}</p>
<button class="btn btn-light" type="button"
onClick="placeDetails()">Details</button>
<button class="btn btn-outline-danger" type="button"
onClick="placeDelete({{id}})">Delete</button>`

function onPlaceClick(event) {
	// open a popup menu about the place
	popMarker = event.target;
	popLocation = popMarker.getLatLng();  // for showPopup
	let content = placePopupContent
		.replace('\{\{name\}\}', popMarker.options.placeName)
		.replace('\{\{id\}\}', popMarker.options.placeID)
		.replace('\{\{type\}\}',
			placeIcons[popMarker.options.placeType].options.placeTypeName);
	popup = popMarker.getPopup();
	if (popup) {
		popMarker.unbindPopup();  // it can't be reopened (?)
	}
	popup = L.popup().setContent(content);
	popMarker.bindPopup(popup)
		.openPopup();
}

function placeDetails() {
	// console.info("popMarker=", popMarker);
	requestUrl = "/routes/place/" + popMarker.options.placeID.toString();
	$.get(requestUrl, null, showPopup, 'html')
		.fail(requestFailMsg);
}

function placeDelete(pk) {
	// request the deletion form (inc csrf token) from the server
	if (pk != popMarker.options.placeID) {
		alert("placeDelete: place id doesn't match:" + pk + " vs. "
			  + popMarker.options.placeID);
	}
	$.get("/routes/place/" + pk.toString() + "/delete", "",
		  placeConfirmDelete, "html", {error: requestFailMsg})
}

function placeConfirmDelete(form) {
	// shows an html form to confirm deletion of a place
	let popup = popMarker.getPopup();
	popup.setContent(form);
}

function onPlaceDoDelete(event) {
	// after confirmation, do the delete (with csrf token)
	//if (confirm("delete " + popMarker.options.placeName + " (pk=" + pk + ")?")
	event.preventDefault();
	let formData = new FormData(event.target);
	let pk = formData.get("pk")
	requestUrl = "/routes/place/" + pk.toString() + "/delete"
	// alert("onPlaceDoDelete: requestUrl=(" + requestUrl);
	postMapDialogData(formData, 'json', function(data) {
		// popMarker.remove();  // this also removes the popup
		placesLayer.removeLayer(popMarker);
	});
}


/* --- place type handling ---
 Any updates to PlaceType refresh the placetype-icon dictionary placeIcon
 and then show the PlaceType list dialog */

function onPlaceTypeEdit(pk) {
	if (!pk) {pk="";}
	getMapDialogData("/routes/place/type/" + pk);
}

function onPlaceTypeSubmit(event) {
	event.preventDefault();
	let formData = new FormData(event.target);
	let pk = formData.get("pk")
	requestUrl = "/routes/place/type/" + (pk ? pk : "");
	postMapDialogData(formData, "text", afterPlaceTypesUpdate);
}

function onPlaceTypeDoDelete(event) {
	event.preventDefault();
		let formData = new FormData(event.target);
		let pk = formData.get("pk")
		if (!pk) {throw "pk is null";}
		requestUrl = "/routes/place/type/" + (pk ? pk : "") + "/delete";
		postMapDialogData(formData, 'text', afterPlaceTypesUpdate);
}

function afterPlaceTypesUpdate(data) {
	// update placeTypes if JSON sent, else show html response in the dialog
	console.info("afterPlaceTypesUpdate:", data);
	try {
		data = JSON.parse(data);  // is it json?
		}
	catch(exc) {
		// Should be a SyntaxError.  treat it as html
		showMapDialog(data);
		return;
	}
	refreshPlaceIconDict(data);
	// refresh the icons & place type names in place layer
	placesLayer.eachLayer(function(feature) {
		let placeTypePK = feature.options.placeType;
		if (!placeTypePK in placeIcons) {
			// placeType has been deleted - set to default placeType
			placeTypePK = placeIcons["default"];  // default pk
			feature.options.placeType = placeTypePK;
		} 
		feature.setIcon(placeIcons[placeTypePK]);
	});
	getMapDialogData("/routes/place/types")
}

/* ---- edit tags for a single track or place ---- */
function editTags(pk, itemtype) {
	// called by clicking a track or place tag
	requestUrl = "/routes/tags/" + itemtype + "/" + pk;
	$.get(requestUrl, null, showMapDialog, 'html')
		.fail(requestFailMsg);
}

function onTagsFormSubmit(event, itemtype) {
	event.preventDefault();
	let formData = new FormData(event.target);
	requestUrl = "/routes/tags/"+ itemtype + "/"+ formData.get('pk');
	postMapDialogData(formData, 'text', showPopup);
	onCloseMapDialog();
}

/* ------ preferences handling ------ */
function onPreference() {
	getMapDialogData("/routes/preference");
}

function onPreferenceSubmit(event) {
	event.preventDefault();
	let formData = new FormData(event.target);
	requestUrl = "/routes/preference";
	postMapDialogData(formData, 'text', afterPreferenceSubmit);
}

function afterPreferenceSubmit(data) {
	// handle either json or html
	try {
		data = JSON.parse(data);
	}
	catch(exc) {
		// it was html (SyntaxError)
		showMapDialog(data);
		return;
	}
	// it was json - update settings and close the preference dialog
	updatePreference(data);
	document.getElementById("map-dialog").close();
}

function updatePreference(data) {
	if (data[0].model != "routes.preference") {
		console.error("Invalid preference data:", data);
		throw "invalid preference data";
	}
	// init preference (a list of 1 item is sent)
	preference = data[0].fields;
}

// ------ general purpose popup & modal dialog handling ------
function showPopup(data) {
	if (!popup) {		
		popup = L.popup();
	}
	popup.setContent(data)
		 .setLatLng(popLocation)
		 .openOn(map);
}

function postMapDialogData(formData, dataType, successRoutine) {
	$.ajax({
						url: requestUrl,
						method: "POST",
						data: formData,
						processData: false,
					    contentType: false,
						dataType: dataType,
						success: successRoutine,
						error: requestFailMsg
					});
}

function getMapDialogData(url) {
	requestUrl = url;
	$.get(requestUrl, null, showMapDialog, "html");
	return false;  // prevent default action
}

function showMapDialog(data) {
	let dialog = document.getElementById("map-dialog");
	dialog.innerHTML = data;
	dialog.showModal();
}

function onCloseMapDialog() {
	document.getElementById("map-dialog").close();
}

function onPlaceMouseOver(ev) {
	layerChangeState(ev.target, 'place', true, null);
	const placeID = ev.target.feature.properties.pk;
	$("#place-sidebar-item-" + placeID).addClass("highlight");
}

function onPlaceMouseLeave(ev) {
	const placeID = ev.target.feature.properties.pk;
	$("#place-sidebar-item-" + placeID).removeClass("highlight");
	layerChangeState(ev.target, 'place', false, null);
}

// ----- control highlighting of places & tracks ------

/* layer highlighting has 4 states, like 4 corners of a square:
   No highlight:   mouse enter -> hovering; select -> selected
   Selected and hovering: mouse leave -> selected; deselect -> hovering
   Selected:  mouse enter -> sel & hovering; deselect -> none
   Hovering:  mouse leave -> none; select -> sel & hovering

   Visually, hovering has precedence, so hover + select looks like hover
*/

function layerChangeState(layer, itemType, hovering, selected) {
	if (!layer.feature) {
		console.error("layerChangeState(", layer, ")");
		throw Error("layerChangeState invalid without layer.feature");
	}
	if (!layer.feature.properties.state) {
		layer.feature.properties.state = {};
	}
	if (hovering !== null) {
		layer.feature.properties.state.hovering = hovering;
	}
	if (selected !== null) {
		layer.feature.properties.state.selected = selected;
	}
	let style = getLayerStyle(itemType, layer.feature.properties.state);
	// console.info("layerStateChange(..",hovering, selected,"): style=", style);
	layerUpdateHilight(layer, itemType, style);
}

const trackHoverStyle = {
	color: 'Indigo',
	opacity: 1.0
};

const trackSelectedStyle = {
	color: 'DeepPink',
	opacity: 1.0
};

const placeHoverStyle = {
	radius: 10,
	stroke: false,
	fill: true,
	fillColor: '#ffff00',  // yellow
	fillOpacity: 0.5,
	interactive: false,   // don't emit mouse events, pass to map
};

const placeSelectedStyle = {
	radius: 10,
	stroke: true,
	weight: 2,  // px
	color: 'DeepPink',   // '#cc00cc',  // grey
	opacity: 1.0,
	fill: false,
	interactive: false,   // don't emit mouse events, pass to map
};

function getLayerStyle(itemType, state) {
	/* return the hilight style, or null if not highlighted */
	// console.info("getLayerStyle(", itemType, state, ")");
	if (state.hovering) {
		return itemType == 'track' ? trackHoverStyle : placeHoverStyle;
	} else if (state.selected) {
		return itemType == 'track' ? trackSelectedStyle : placeSelectedStyle;
	} else {
		return null;
	}
}

function layerUpdateHilight(layer, itemType, style) {
	if (itemType == 'track') {
		if (style) {
			layer.setStyle(style);
			layer.bringToFront();
		} else {
			tracksLayer.resetStyle(layer);
		}
	} else if (itemType == 'place') {
		if (layer.feature.properties.prevHilight) {
			layer.feature.properties.prevHilight.removeFrom(placesLayer);
		}
		if (style) {
			let hilight = L.circleMarker(layer.getLatLng(), style);
			hilight.addTo(placesLayer);
			layer.feature.properties.prevHilight = hilight;
		} else {
			layer.feature.properties.prevHilight = null;
		}
	}
}


// ---- utilities ----

function formArrayToJSON(arrayData) {
	// convert an array of {name: value: } dicts to a single dict {name: value}
	result = {};

	arrayData.forEach(function(fieldData) {
		result[fieldData['name']] = fieldData['value'];
	});

	/* $.map(arrayData, function(fieldData) {
		result[fieldData['name']] = fieldData['value'];
	}); */

	return result;
}
