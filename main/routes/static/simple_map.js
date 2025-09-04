/**
 * Script for displaying a simple map with features specified in the "featureCollection"
 * document element.
 * 
 * Requires: leaflet css & js, and jquery js to be imported first
 * also needs a <div id="map"> with fixed width to be defined
 * 
 */
var featureCollection;
var map;
var featuresLayer;

$(document).ready(function() {
	setupMap();
	showFeatureCollection();
})

function setupMap() {
	map = L.map('map').setView([51.505, -0.09], 13);
	L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
	    maxZoom: 19,
	    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
	}).addTo(map);
}

function showFeatureCollection() {
	featureCollection = JSON.parse(
		document.getElementById('featureCollection').textContent);
	
	if (featureCollection) {
		featuresLayer = L.geoJSON(featureCollection, {
			style: {color: '#ff0000',
			    weight: 1,
			    opacity: 0.5
			} 
		}).addTo(map);
		if ("bbox" in featureCollection){
			map.fitBounds(featureCollection["bbox"]);
		}
	} else {
		console.warn("No map features in featureCollection");
	}
}
