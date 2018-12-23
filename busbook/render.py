import errno
from datetime import datetime
from itertools import tee
from shutil import rmtree, copytree

import networkx
from jinja2 import Environment, PackageLoader, select_autoescape
from pathlib2 import Path


STATIC_DIR = Path(__file__).parent/'static'


def render(gtfs, date=datetime.today(), outdir=Path('.')):
    clear_out(outdir)
    env = Environment(loader=PackageLoader('busbook', 'templates'),
                      autoescape=select_autoescape(['html']))
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

    def get_trips_by_direction(service_period):
        trips = [trip for trip in gtfs.GetTripList()
                 if trip.route_id == route.route_id
                    and trip.service_id == service_period.service_id]
        return separate_trips(trips)

    def timetable_timepoints(trips):
        # Compare by name to handle multi-platform stations.
        sequences = [[stop.stop_name.strip() for stop in timepoint_sequence(trip)]
                     for trip in trips]
        result = unite(*sequences)
        return [next(stop for stop in gtfs.GetStopList()
                     if stop.stop_name.strip() == stop_name) for stop_name in result]

    def timetable_rows(trips, timepoints):
        trips = sort_trips(trips, timepoints)
        rows = [[get_stop_time(trip, timepoint) for timepoint in timepoints]
                for trip in trips]
        """
        rows = []
        for trip in sort_trips(trips, timepoints):
            row = [None]*len(timepoints)
            p = 0
            for st in trip.GetStopTimes():
                if st.stop in timepoints[p:]:
                    idx = p + timepoints[p:].index(st.stop)
                    row[idx] = st.arrival_secs or st.departure_secs
                    p = idx
            rows.append(row)
        """
        return rows

    def sort_trips(trips, timepoints):
        # Sort by departure, which puts the trips in order, but not necessarily
        # with the earliest trip first.
        common_tp = next(
            (tp for tp in timepoints
             if all(get_stop_time(trip, tp) is not None for trip in trips)),
            None)
        #if common_tp is None:
        #    return sorted(trips, key=lambda trip: trip.trip_id)
        assert common_tp is not None
        trips = sorted(trips, key=lambda trip: get_stop_time(trip, common_tp))

        # Find the largest gap between trips and make that daybreak.
        def diff_secs(s1, s2):
            return min(abs(s1 - s2),
                       abs(s1 - (s2 + 24*60*60)),
                       abs(s1 - (s2 - 24*60*60)))
        # Be conservative - don't reorder the list if there isn't an obvious gap.
        indices = [(-1, 0)] + [(i, i + 1) for i in range(len(trips) - 1)]
        split = max_gap = 0
        for i1, i2 in indices:
            gap = diff_secs(get_stop_time(trips[i1], common_tp),
                            get_stop_time(trips[i2], common_tp))
            if gap > max_gap:
                max_gap = gap
                split = i2
        return trips[split:] + trips[:split]

    def get_stop_time(trip, stop):
        # Assume GetStopTimes() returns stops in order (see trip.GetPattern).
        # Compare by name to handle multi-platform stations.
        st = next((st for st in trip.GetStopTimes()
                   if st.stop.stop_name.strip() == stop.stop_name.strip()), None)
        if st is None:
            return None
        else:
            return st.arrival_secs or st.departure_secs

    def format_time(secs):
        hours = secs // 3600
        minutes = secs // 60 % 60
        if hours == 0:
            return '12:%02d' % minutes
        elif hours > 12:
            return '%d:%02d' % (hours - 12, minutes)
        else:
            return '%d:%02d' % (hours, minutes)

    def weekdays(service_period):
        DAYS = ['M', 'Tu', 'W', 'Th', 'F', 'Sa', 'Su']
        return (DAYS[i] for i, applies in enumerate(service_period.day_of_week)
                if applies)

    # Handle routes without a specified agency.
    agency = next((agency for agency in gtfs.GetAgencyList()
                   if agency.agency_id == route.agency_id), gtfs.GetDefaultAgency())
    write_out(
        outdir/'routes'/('%s-%s.html' % (agency.agency_id, route.route_id)),
        env.get_template('route.html').render(
            gtfs=gtfs,
            service_periods=service_periods,
            route=route,
            agency=agency,
            get_trips_by_direction=get_trips_by_direction,
            timetable_timepoints=timetable_timepoints,
            timetable_rows=timetable_rows,
            format_time=format_time,
            weekdays=weekdays))


def separate_trips(trips):
    """
    Separate trips into up to two distinct directions. Rationale: Some feeds misuse
    the direction_id flag.
    """
    if len(trips) == 0:
        return []

    iter_trips = iter(trips)
    first_trip = next(iter_trips)
    directions = [
        (timepoint_sequence(first_trip), [first_trip])
        ]
    for trip in iter_trips:
        trip_sequence = timepoint_sequence(trip)
        direction_sequences = [unite(common_sequence, trip_sequence)
                               for common_sequence, trips in directions]
        direction_add_lengths = [len(direction_sequences[idx]) - len(common_sequence)
                                 for idx, (common_sequence, trips)
                                 in enumerate(directions)]
        min_idx, min_add_length = min(enumerate(direction_add_lengths),
                                      key=lambda (i, v): v)
        if min_add_length >= len(trip_sequence) - 1:
            directions.append((trip_sequence, [trip]))
        else:
            min_sequence, min_trips = directions[min_idx]
            directions[min_idx] = (direction_sequences[min_idx], min_trips + [trip])

    named_directions = []
    for common_sequence, trip_list in directions:
        headsigns = set([trip.trip_headsign for trip in trip_list])
        named_directions.append(('/'.join(sorted(headsigns)), trip_list))
    return sorted(named_directions, key=lambda (headsigns, trip_list): headsigns)


def timepoint_sequence(trip):
    def is_timepoint(stop_time):
        if stop_time.timepoint == 1:
            return True
        elif (stop_time.timepoint is None
              and stop_time.arrival_secs is not None
              and stop_time.departure_secs is not None):
            return True
        else:
            return False
    # Assume GetStopTimes() returns stops in order (see trip.GetPattern).
    return [st.stop for st in trip.GetStopTimes() if is_timepoint(st)]


def unite(*sequences):
    graph = networkx.DiGraph()

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
            new_node = next((node for node, item in node_item.iteritems()
                             if item == this_item
                                and not networkx.has_path(graph, node, last_node)),
                            None)
            if new_node is None:
                new_node = next_node
                node_item[next_node] = this_item
                next_node += 1
            if not graph.has_edge(last_node, new_node):
                graph.add_edge(last_node, new_node)
            last_node = new_node

    topo_sort = networkx.topological_sort(graph)
    return [node_item[node] for node in topo_sort]


def write_out(path, contents):
    path.parent.mkdir(exist_ok=True)
    with path.resolve().open('wt') as fd:
        fd.write(contents)

