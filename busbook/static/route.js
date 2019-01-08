BodyStyle = getComputedStyle(document.body)
RouteColor = BodyStyle.getPropertyValue("--route-color");
RouteTextColor = BodyStyle.getPropertyValue("--route-text-color");

RouteTabs = new Tabs(document.getElementsByTagName("section"));
Header = document.getElementsByTagName("header")[0];
Header.appendChild(RouteTabs.navigation);

const OsmLayer = new L.TileLayer(
        "https://{s}.tile.openstreetmap.se/hydda/full/{z}/{x}/{y}.png",
        { attribution: 'Map &copy; <a href="https://openstreetmap.org">'
                        + 'OpenStreetMap</a>' });
RouteMap = L.map("route-map", { fullscreenControl: { pseudoFullscreen: true } })
        .addLayer(OsmLayer)
L.control.layers({ "OpenStreetMap": OsmLayer })
        .addTo(RouteMap);
RouteBounds = new L.LatLngBounds(Stops.map(stop => [stop.stop_lat, stop.stop_lon]));
RouteMap.fitBounds(RouteBounds);

function MakeTooltip(stop, layer) {
        layer.bindTooltip(stop.stop_name);
        return layer;
}
L.polyline(Shapes, { color: RouteColor })
        .addTo(RouteMap);
Stops.forEach(function (stop) {
        var marker;
        if (Timepoints.find(timepoint => timepoint.stop_id === stop.stop_id)
            === undefined) {
                marker = L.circleMarker([stop.stop_lat, stop.stop_lon],
                                        { radius: 8,
                                          stroke: true,
                                          color: RouteTextColor,
                                          fillColor: RouteColor,
                                          fillOpacity: 1.0 })
                        .addTo(RouteMap);
                MakeTooltip(stop, marker);
        }
});
Timepoints.forEach(function (stop) {
        var marker = L.marker([stop.stop_lat, stop.stop_lon], title=stop.stop_name)
                .addTo(RouteMap);
        MakeTooltip(stop, marker);
});
