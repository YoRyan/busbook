# -*- coding: utf-8 -*-
import errno
import re
from datetime import datetime
from itertools import tee
from shutil import rmtree, copytree

import networkx
import jinja2
from pathlib2 import Path


STATIC_DIR = Path(__file__).parent/'static'


class RouteSchedule(object):

    _DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    def __init__(self, gtfs, route, services):
        self.agency = next((agency for agency in gtfs.GetAgencyList()
                            if agency.agency_id == route.agency_id),
                           gtfs.GetDefaultAgency())
        self.route = route

        # Create a schedule for every day of the week.
        periods = []
        all_trips = [trip for trip in gtfs.GetTripList()
                     if trip.route_id == route.route_id]
        for i in range(7):
            service_ids = [service.service_id for service in services
                           if service.day_of_week[i] == 1
                              or service.day_of_week == [0]*7]
            trips = [trip for trip in all_trips if trip.service_id in service_ids]
            if len(trips) > 0:
                periods.append(ServicePeriod('', trips))

        # Consolidate similar schedules.
        self.service_periods = []
        to_examine = range(len(periods))
        while len(to_examine) > 0:
            this = to_examine.pop(0)
            similar = [other for other in to_examine
                       if periods[this] == periods[other]]
            for other in similar:
                to_examine.remove(other)

            period = periods[this]
            day_of_week = [int(i == this or i in similar)
                           for i in range(len(periods))]
            period.rename(self._week_range(day_of_week))
            self.service_periods.append(period)

    def _week_range(self, day_of_week):
        cont_ranges = []
        range_begin = None
        for i, b in enumerate(day_of_week):
            if b and range_begin is None:
                range_begin = i
            elif not b and range_begin is not None:
                cont_ranges.append((range_begin, i - 1))
                range_begin = None
        if range_begin is not None:
            cont_ranges.append((range_begin, i))

        def name(begin, end):
            if begin == end:
                return RouteSchedule._DAYS[begin]
            else:
                return ('%s - %s'
                        % (RouteSchedule._DAYS[begin], RouteSchedule._DAYS[end]))
        if len(cont_ranges) == 0:
            return name(0, -1)
        else:
            return ', '.join(name(*cont_range) for cont_range in cont_ranges)


class ServicePeriod(object):

    def __init__(self, name, trips):
        self.rename(name)
        directions = []
        for trip_list in self._separate(trips):
            headsigns = set(trip.trip_headsign or trip.GetPattern()[-1].stop_name
                            for trip in trip_list)
            direction = '/'.join(sorted(headsigns))
            timetable = Timetable(trip_list)
            directions.append((direction, timetable))
        self.directions = sorted(directions, key=lambda (d, t): d)

    def rename(self, name):
        self.name = name
        self.slug = re.sub(r'[^a-zA-Z]', '', name)

    def _separate(self, trips):
        """Separate trips into up to two distinct directions. Rationale: Some
        feeds misuse the direction_id flag.
        """
        if len(trips) == 0:
            return []
        iter_trips = iter(trips)
        first_trip = next(iter_trips)
        directions = [
            (timepoint_stops(first_trip), [first_trip])
            ]
        for trip in iter_trips:
            trip_sequence = timepoint_stops(trip)
            direction_sequences = [unite(common_sequence, trip_sequence)
                                   for common_sequence, trips in directions]
            direction_add_lengths = [len(direction_sequences[idx])
                                     - len(common_sequence)
                                     for idx, (common_sequence, trips)
                                     in enumerate(directions)]
            min_idx, min_add_length = min(enumerate(direction_add_lengths),
                                          key=lambda (i, v): v)
            if min_add_length >= len(trip_sequence) - 1:
                directions.append((trip_sequence, [trip]))
            else:
                min_sequence, min_trips = directions[min_idx]
                directions[min_idx] = (direction_sequences[min_idx],
                                       min_trips + [trip])
        return [trip_list for sequence, trip_list in directions]

    def __eq__(self, other):
        return self.directions == other.directions


class Timetable(object):

    NO_SERVICE = object()
    SKIP = object()

    def __init__(self, trips):
        stop_times = {trip: [st for st in timepoint_stop_times(trip)]
                      for trip in trips}
        timepoints = {trip: [st.stop for st in trip_stop_times]
                      for trip, trip_stop_times in stop_times.iteritems()}

        # Find common timepoints for the header.
        self.timepoints = unite(*timepoints.values())

        # Populate rows.
        self.rows = []
        for trip in self._sort(trips):
            row = []
            timepoint = -1
            for stop_time in stop_times[trip]:
                slice_timepoint = (self.timepoints[timepoint + 1:]
                    .index(stop_time.stop))
                if timepoint == -1:
                    row = [Timetable.NO_SERVICE]*slice_timepoint
                else:
                    row += [Timetable.SKIP]*slice_timepoint
                row += [self._time(stop_time)]
                timepoint += slice_timepoint + 1
            row += [Timetable.NO_SERVICE]*(len(self.timepoints) - timepoint - 1)
            self.rows.append(row)

    def _sort(self, trips):
        # Create a directed graph where each node is a trip.
        graph = networkx.DiGraph()
        node_trip = {n: trip for n, trip in enumerate(trips)}
        trip_node = {trip: n for n, trip in enumerate(trips)}
        for node in node_trip.keys():
            graph.add_node(node)

        # Add edges to represent relative orderings at common timepoints.
        stop_times = {trip: [st for st in timepoint_stop_times(trip)]
                      for trip in trips}
        timepoints = {trip: [st.stop for st in trip_stop_times]
                      for trip, trip_stop_times in stop_times.iteritems()}
        for this_trip in trips:
            this_node = trip_node[this_trip]
            other_trips = list(trips)
            for stop_time in stop_times[this_trip]:
                for other_trip in (trip for trip in list(other_trips)
                                   if stop_time.stop in timepoints[trip]):
                    other_stop_time = next(st for st in stop_times[other_trip]
                                           if st.stop == stop_time.stop)
                    other_node = trip_node[other_trip]
                    if (self._time(stop_time) < self._time(other_stop_time)
                            and not networkx.has_path(graph, other_node, this_node)
                            and not graph.has_edge(this_node, other_node)):
                        graph.add_edge(this_node, other_node)
                    other_trips.remove(other_trip)
                if len(other_trips) == 0:
                    break

        # Sort the graph, recreate the list.
        topo_sort = networkx.topological_sort(graph)
        return [node_trip[node] for node in topo_sort]

    def _time(self, stop_time):
        return stop_time.departure_secs or stop_time.arrival_secs

    def __eq__(self, other):
        return self.timepoints == other.timepoints and self.rows == other.rows


def render(gtfs, date=datetime.today(), outdir=Path('.')):
    clear_out(outdir)
    env = jinja2.Environment(
        loader=jinja2.PackageLoader('busbook', 'templates'),
        autoescape=jinja2.select_autoescape(['html']),
        trim_blocks=True,
        lstrip_blocks=True)

    @jinja2.evalcontextfilter
    def make_breaks(eval_ctx, s):
        res = re.sub(
            r'(&amp;|@|-|/)', r'\1' + jinja2.Markup('&#8203;'), jinja2.escape(s))
        if eval_ctx.autoescape:
            res = jinja2.Markup(res)
        return res
    env.filters['break'] = make_breaks

    @jinja2.evalcontextfilter
    def format_time(eval_ctx, secs):
        hours = secs // 3600 % 24
        minutes = secs // 60 % 60
        if hours == 0:
            s = '12:%02d' % minutes
        elif hours > 12:
            s = '%d:%02d' % (hours - 12, minutes)
        else:
            s = '%d:%02d' % (hours, minutes)
        if hours < 12:
            res = jinja2.Markup('<span class="time-am">%s</span>' % s)
        else:
            res = jinja2.Markup('<span class="time-pm">%s</span>' % s)
        if eval_ctx.autoescape:
            res = jinja2.Markup(res)
        return res
    env.filters['time'] = format_time

    def route_css(route):
        if route.route_color and route.route_text_color:
            return ('--route-color: #%s; --route-text-color: #%s;'
                    % (route.route_color, route.route_text_color))
        elif route.route_color:
            return '--route-color: #%s;' % route.route_color
        else:
            return ''
    env.filters['route_css'] = route_css

    render_index(env, gtfs, outdir=outdir)
    for route in gtfs.GetRouteList():
        render_route(env, gtfs, effective_services(gtfs, date), route,
                     outdir=outdir)


def clear_out(path):
    try:
        rmtree(str(path.resolve()))
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
    copytree(str(STATIC_DIR), str(path/'static'))


def effective_services(gtfs, date):
    def parse(datestr):
        return datetime.strptime(datestr, '%Y%m%d')
    return [sp for sp in gtfs.GetServicePeriodList()
            if sp.start_date is None
               or (date >= parse(sp.start_date)
                   and date <= parse(sp.end_date).replace(hour=23, minute=59))]


def render_index(env, gtfs, outdir=Path('.')):
    def get_routes(agency_id):
        all_routes = gtfs.GetRouteList()
        routes = [route for route in all_routes
                  if route.agency_id == agency_id]

        # Handle routes without a specified agency.
        default_agency = gtfs.GetDefaultAgency()
        if agency_id == default_agency.agency_id:
            routes += [route for route in all_routes
                       if route.agency_id == '']

        return sorted(routes, key=lambda route: route.route_id)

    write_out(
        outdir/'index.html',
        env.get_template('index.html').render(
            gtfs=gtfs,
            agencies=', '.join(agency.agency_name
                               for agency in gtfs.GetAgencyList()),
            get_routes=get_routes))


def render_route(env, gtfs, service_periods, route, outdir=Path('.')):
    if len(service_periods) == 0:
        print('WARNING: No service scheduled for %s %s.'
              % (route.route_short_name, route.route_long_name))
        return
    else:
        print('Processing %s %s.'
              % (route.route_short_name, route.route_long_name))

    schedule = RouteSchedule(gtfs, route, services=service_periods)
    write_out(
        outdir/'routes'/('%s-%s.html' % (schedule.agency.agency_id, route.route_id)),
        env.get_template('route.html').render(
            gtfs=gtfs,
            schedule=schedule,
            Timetable=Timetable))


def timepoint_stops(trip):
    return [stop_time.stop for stop_time in timepoint_stop_times(trip)]


def timepoint_stop_times(trip):
    timepoint_flag = (
        lambda stop_times: all(st.timepoint is not None for st in stop_times),
        lambda stop_time: stop_time.timepoint == 1
        )
    human_times = (
        lambda stop_times: any(st.departure_time[-2:] != '00' for st in stop_times),
        lambda stop_time: ((stop_time.arrival_time is not None
                            and stop_time.arrival_time[-2:] == '00')
                           or (stop_time.departure_time is not None
                               and stop_time.departure_time[-2:] == '00'))
        )
    strategies = [timepoint_flag, human_times]
    # Assume GetStopTimes() returns stops in order (see trip.GetPattern).
    stop_times = trip.GetStopTimes()
    for precondition, classifier in strategies:
        if precondition(stop_times):
            timepoints = [st for st in stop_times if classifier(st)]
            if len(timepoints) >= 2:
                return timepoints
    return stop_times


def unite(*sequences):
    # Create a directed graph where each node is an item in a sequence.
    graph = networkx.DiGraph()

    # Add edges to represent relative orderings at common items.
    all_items = reduce(lambda s1, s2: s1.union(s2),
                       (set(sequence) for sequence in sequences))
    node_item = {n: item for n, item in enumerate(all_items)}
    for node in node_item.keys():
        graph.add_node(node)
    next_node = len(all_items)
    for sequence in sequences:
        items = iter(sequence)
        try:
            first_item = next(items)
        except StopIteration:
            break
        last_node = min(node for node, item in node_item.iteritems()
                        if item == first_item)
        for this_item in items:
            try:
                new_node = min(node for node, item in node_item.iteritems()
                               if item == this_item
                                  and not networkx.has_path(graph, node, last_node))
            except ValueError: # No node found.
                new_node = next_node
                node_item[next_node] = this_item
                next_node += 1
            if not graph.has_edge(last_node, new_node):
                graph.add_edge(last_node, new_node)
            last_node = new_node

    # Sort the graph, return the sorted list.
    topo_sort = networkx.topological_sort(graph)
    return [node_item[node] for node in topo_sort]


def write_out(path, contents):
    path.parent.mkdir(exist_ok=True)
    with path.resolve().open('wt') as fd:
        fd.write(contents)

