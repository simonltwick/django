let popup;  		//displayed popup
let popMarker;		//marker of last popup
let popLocation;	//location of last popup

let dragStartLatLng;  // start of drag action for place

let nearbyTracksUrl;  // url for searching tracks

let preference;  // nearby search preference

let trackSearchHistory = '';
let placeSearchHistory = '';


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
		this.container.addEventListener("click", this.onClick);
		return this.container;
	}
	onClick(event) {
		// toggle the navbar visibility
		L.DomEvent.stopPropagation(event);
		// hiding/unhiding of base-header is also done by showMessages
		// in bike.js
		document.getElementById("base-header").classList.toggle("d-none");
	}
}

const navControl = new NavControl({position: "topright"}).addTo(map);

const trackStyle = {color: '#ff00ff',
    weight: 3,
    opacity: 0.5
};
const startMarkerStyle = {
	radius: 2,  // should be bigger than the track style
	weight: 1,  // line around circumference
	opacity: 0.5,
	color: "#00ff00",
	fill: true,
	fillOpacity: 0.5
	};
const stopMarkerStyle = {
	radius: 2,  // should be bigger than the track style
	weight: 1,  // line around circumference
	opacity: 0.5,
	color: "#ff0000",  // for fill and circumference
	fill: true,
	fillOpacity: 0.5
	};

// add layers for tracks & places

let placeIcons;
let placesLayer = L.geoJSON().addTo(map);   // map layer for places
layerControl.addOverlay(placesLayer, "Places");
let tracksLayer = L.geoJSON().addTo(map); 
layerControl.addOverlay(tracksLayer, "Tracks");
let tracksHidden = [];
let boundaries = L.geoJSON().addTo(map);  // for (search) boundaries


// show initial tracks/places, or if none, show welcome dialog
let dialog = document.getElementById("map-dialog");
const initialTracks = JSON.parse(document.getElementById('initialTracks'
	).textContent);
const initialPlaces = JSON.parse(document.getElementById('initialPlaces'
	).textContent);

if (initialTracks) {
	showTracks(initialTracks);
} else if (initialPlaces) {
	// do nothing - they are shown in buildPlaceIconDict later.
} else {
	/* show map dialog, pre-populated with a help/info message */
	try {
		const initBounds = JSON.parse(document.getElementById('initBounds'
			).textContent);
		map.fitBounds(initBounds);
	} catch {
		map.fitWorld();
	}
	dialog.showModal();
}

// was the map initialised for a search?  if so, show the search dialog
const initSearch = JSON.parse(document.getElementById('initSearch').textContent);
if (initSearch) {
	onRoutesSearch();
}

// init preferences & place icons
// get preference & buildPlaceIcons cannot be run in parallel
$.get("/routes/api/preference", "json", function(data){
	updatePreference(data);
	buildPlaceIcons();
});

function buildPlaceIcons() {
	$.get('/routes/api/place/types/icons', null, buildPlaceIconDict, 'json');
	// nb. placeIcons is not initialised until response received
}

function buildPlaceIconDict(data) {
	refreshPlaceIconDict(data);
	// console.info("buildPlaceIconDict:", data, placeIcons);
	if (initialPlaces) {
		showPlaces(initialPlaces);
	}
}


/* ----- end of initialisation ------ */

function setMapBounds() {
	// resize the map to fit placesBounds and tracksBounds
	let trackBounds = tracksLayer.getLayers().length ? tracksLayer.getBounds(): null;
	let placeBounds = placesLayer.getLayers().length ? placesLayer.getBounds(): null;
	let combinedBounds = (trackBounds? (
		placeBounds? placeBounds.extend(trackBounds) : trackBounds
		) : placeBounds); 
	if (combinedBounds) {
		map.fitBounds(combinedBounds);
	} else {
		console.error("map bounds not defined:", trackBounds, placeBounds);
		map.fitWorld();
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

const nearbyButtonsTemplate = 	`<p>
	<div class="btn-group" role="group">
	<button onClick="nearbyTracks()" class="btn btn-outline-secondary">
	  Nearby Tracks</button>
	  {{ track_dropdown }}
	</div>
	<div class="btn-group" role="group">
	<button class="btn btn-outline-secondary" onClick="nearbyPlaces()">
	Nearby Places</button>
	{{ place_dropdown }}
	<div>
	</p>`;

const trackDropdownButtons = `<button type="button" 
    class="btn btn-outline-secondary dropdown-toggle"
	data-toggle="dropdown" aria-expanded="false" aria-haspopup="true"
	id="nearby-tracks1">
    <!-- <span class="invisible">Toggle Dropdown</span> -->
  </button>
  <div class="dropdown-menu" aria-labelledby="nearby-tracks1">
    <a href="#" class="btn btn-outline-secondary dropdown-item"
		onClick="nearbyTracks('or')">
	  	Add to tracks already found</a>
    <a href="#" class="btn btn-outline-secondary dropdown-item" 
		onClick="nearbyTracks('and')">
	  	Search only tracks already found</button></a>
  </div>`;

const placeDropdownButtons =   `<button type="button" 
      class="btn btn-outline-secondary dropdown-toggle"
  	data-toggle="dropdown" aria-expanded="false" aria-haspopup="true"
  	id="nearby-places1">
      <!-- <span class="invisible">Toggle Dropdown</span> -->
    </button>
    <div class="dropdown-menu" aria-labelledby="nearby-places1">
      <a href="#" class="btn btn-outline-secondary dropdown-item"
  		onClick="nearbyPlaces('or')">
  	  	Add to places already found</a>
      <a href="#" class="btn btn-outline-secondary dropdown-item" 
  		onClick="nearbyPlaces('and')">
  	  	Search only places already found</button></a>
    </div>`;
  
function getNearbyButtons(){
	const trackButtonDropdown = (trackSearchHistory ? trackDropdownButtons:'');
	const placeButtonDropdown = (placeSearchHistory ? placeDropdownButtons:'');
	return nearbyButtonsTemplate.replace(
		'{{ track_dropdown }}', trackButtonDropdown
		).replace('{{ place_dropdown }}', placeButtonDropdown);
}
	
function onMapClick(event) {
	popLocation = event.latlng;
	const buttonsHtml = getNearbyButtons();
	popup = L.popup()
		.setLatLng(popLocation)
		.setContent(
			'<p>You clicked at ' + popLocation.toString()
			+ mapClickPopupContent
			+ buttonsHtml)
		.openOn(map);
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


/* ----- search handling ----- */
function onRoutesSearch() {
	// search tracks or places from a form.
	const params = {track_search_history: trackSearchHistory? "1":"",
					place_search_history: placeSearchHistory? "1":""
	}
	getMapDialogData("/routes/api/search?" + $.param(params));
	if (popup) {
		popup.close();
	}
}

function onRefreshBoundaryNames() {
	/* update the boundary names select field in the search dialog, 
	corresponding to the chosen boundary category */
	let boundaryCategory = $("#id_boundary_category").find(":selected").text();
	requestUrl = '/routes/api/boundary/category/' + boundaryCategory + '/names'
	$.get(requestUrl, null, refreshBoundaryNames, 'html').fail(requestFailMsg);
}

function refreshBoundaryNames(data) {
	/* update the boundary names select field with the supplied data */
	$("#id_boundary_name").html(data);
}

function onSearchFormSubmit(event, joinType) {
	event.preventDefault();
	let searchType = document.getElementById("tracks-search"
		).classList.contains("active") ? 'track': 'place'
	let params = {search_type: searchType, join: joinType};
	if (joinType) {
		params["search_history"] = JSON.stringify((searchType == "track") ?
			trackSearchHistory:placeSearchHistory);
	}
	
	requestUrl = '/routes/api/search?' + $.param(params);
	$.post(requestUrl, $('#searchForm').serialize(), searchResults, null
		).fail(requestFailMsg); 
	if (searchType == "track") {
		tracksLayer.clearLayers();
	} else {
		placesLayer.clearLayers();
	}
	/* this automatically parses result data to json or html/text */
}

function searchFormSubmitJson(searchType){
	/* create and send a Search json object */
}

function searchResults(data) {
	// handle search results, which could be html if form errors, or json
	if (!data.status) { // ParseError: html was returned
		showMapDialog(data);
		return;
	}
	// json data was returned, so display it
	onCloseMapDialog();
	var result_type = (data.hasOwnProperty("tracks") ? "tracks":
						(data.hasOwnProperty("places") ? "places": '?'))
						
	if (data["result_count"] == 0) {
		displayMessage("no matching " + result_type, "text-warning");
		return
	}
	displaySearchResultsInfo(data, result_type);
	showBoundary(data);
	if (result_type == "tracks")  {
		trackSearchHistory = data["search_history"];
		showTracks(data["tracks"]);
	} else if (result_type == "places") {
		placeSearchHistory = data["search_history"];
		showPlaces(data["places"]);
	} else {
		console.error("Unrecognised search results:", data);
		log_error("Unrecognised response to search request");
	}
}

function displaySearchResultsInfo(data, result_type) {
	/* display a console message and if results are truncated, a message in the
	messages area */
	if (data["result_count"] > data["result_limit"]) {
		let msg = ("showing " + data["result_limit"] + " of " +
			data["result_count"] + " " + result_type);
		displayMessage(msg, "text-warning");
		console.warn("displaySearchResultsInfo:", msg);
		return;	
	}
	console.info("displaySearchResultsInfo: showing " + data["result_count"]
		+ " " + result_type);
}

function showBoundary(data) {
	boundaries.remove();
	if (data.hasOwnProperty("boundary") && data["boundary"]) {
		boundaries = L.geoJSON(data["boundary"], {
				style: {color: '#ff0000',
						weight: 1,
						opacity: 0.5
						} ,
		}).addTo(map);
	}
}

// error handling
function requestFailMsg(jqXHR, textStatus, errorThrown) {
	console.debug("Request failed:",
		{jqXHR: jqXHR, textStatus: textStatus, errorThrown: errorThrown,
		 requestURL: requestUrl
		});
	if (jqXHR.responseText.startsWith("<!DOCTYPE html>")) {
		// it's an unexpected html failure message, could be django debug info
		document.open()
		document.write(jqXHR.responseText);
		document.close()
		return
	}
	let msg = jqXHR;
	if (jqXHR.status) {
		msg = "Status code " + jqXHR.status + ": " + (jqXHR.responseText ? jqXHR.responseText: jqXHR.statusText);
	}
	log_error(msg);
}

function log_error(msg) {
	console.error(msg, "; from server request=", requestUrl);
	console.info("trackSearchHistory=", trackSearchHistory);
	displayMessage("Error: " + msg, "text-error");
}


/* ------ Track handling ------ */
function nearbyTracks(joinType) {
	/* get tracks nearby popLocation.   depending on the value of searchType,
	add to tracks already shown, replace tracks already shown, or limit the
	search to those already shown.  This is done by resubmitting the 
	query with the combined search term */
	params = {latlon: popLocation.lat + ',' + popLocation.lng}
	if (joinType) {
		params["join"] = joinType;
		params["search_history"] = JSON.stringify(trackSearchHistory);
	}
	requestUrl = '/routes/api/track?' + $.param(params);
	$.get(requestUrl, null, searchResults, 'json').fail(requestFailMsg);
	map.closePopup();
	// add search area to map
	tracksLayer.clearLayers();
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
		displayMessage("No matching tracks found");
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
	setMapBounds();
}

function onTrackShow(feature, layer) {
	if (feature.geometry && feature.geometry.type
			&& feature.geometry.type == "MultiLineString") {
		addTrackStartStopMarkers(feature, layer);
	}
	
	layer.on({
		click: onTrackClick,
		mouseover: onTrackMouseOver,
		mouseout: onTrackMouseLeave,
		});
	// addToTrackSidebar(feature, layer);
}

function addTrackStartStopMarkers(feature, _layer) {
	// add start & stop markers to the layer representation of a track
	let startStopMarkers = [];
	feature.geometry.coordinates.forEach(function(trackSegCoords) {
		if (trackSegCoords.length) {
			let startLatLng = [trackSegCoords[0][1], trackSegCoords[0][0]];
			let startMarker = L.circleMarker(startLatLng, startMarkerStyle)
				.addTo(tracksLayer);
			let end = trackSegCoords.length -1;
			let stopLatLng = [trackSegCoords[end][1], trackSegCoords[end][0]];
			let stopMarker = L.circleMarker(stopLatLng, stopMarkerStyle)
				.addTo(tracksLayer);
			startStopMarkers.push([startMarker, stopMarker]);
		}
	});
	feature.properties.startStopMarkers = startStopMarkers;
}


function trackHide(marker) {
	if (!marker) {
		marker = popMarker;
	}
	// only tracks have marker.feature.properties (search circle doesn't)
	if (!(marker.feature && marker.feature.properties)) {
		return;
	}
	tracksHidden.push(marker);
	removeTrack(marker);
	//tracksGeoLayer.remove(marker);  // removes the whole tracksGeoLayer
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

function removeTrack(marker) {
	marker.removeFrom(tracksLayer);
	if (marker.feature.properties.startStopMarkers) {
		for (const startStopMarker
				of marker.feature.properties.startStopMarkers) {
			startStopMarker[0].removeFrom(tracksLayer);
			startStopMarker[1].removeFrom(tracksLayer);
		}
	}
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
	if (pk == "None") {
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
	requestUrl = "/routes/track/" + (pk ? pk: "")
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

function onTrackRequestDelete(trackPk) {
	requestUrl = "/routes/api/track/" + trackPk + "/delete"
	$.get(requestUrl, null, showPopup, 'html')
		.fail(requestFailMsg);
}

function onTrackConfirmDelete(event, pk) {
	event.preventDefault();
	requestUrl = "/routes/api/track/" + pk + "/delete"
	$.post(requestUrl, $('#trackDeleteForm').serialize(), onTrackDeleted,
			).fail(requestFailMsg); 
}

function onTrackDeleted(data) {
	if (data) {
		// unexpected html returned
		showPopup(data)
	} else {
		displayMessage("Track deleted.");
		removeTrack(popMarker);
		popup.close();
	}
}


/*
// ------ place handling ------
*/
function nearbyPlaces(joinType) {
	/* get places nearby popLocation.   depending on the value of searchType,
	add to places already shown, replace places already shown, or limit the
	search to those already shown.  This is done by resubmitting the 
	query with the combined search term */
	params = {latlon: popLocation.lat + ',' + popLocation.lng}
		if (joinType) {
			params["join"] = joinType;
			params["search_history"] = JSON.stringify(placeSearchHistory);
		}
		requestUrl = '/routes/api/place?' + $.param(params);
	$.get(requestUrl, null, searchResults, 'json').fail(requestFailMsg);
	map.closePopup();
	// add search area to map
	placesLayer.clearLayers();
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
	// console.info("afterPlaceTypesUpdate:", data);
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
		console.error("Invalid preference data:", data, "data[0]=", data[0]);
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
