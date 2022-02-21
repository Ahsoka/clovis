import json
import pytz

locations = {
    'africa',
    'america',
    'antarctica',
    'arctic',
    'asia',
    'atlantic',
    'australia',
    'canada',
    'europe',
    # 'gmt',
    'indian',
    'pacific',
    'us',
    'america/argentina',
    'america/indiana',
    'america/kentucky',
    'america/north dakota',
    'america/indiana'
}

timezones = {location: [] for location in locations}

for timezone in pytz.common_timezones:
    # print(f"{timezone=}")
    for location in locations:
        # print(f"{location=}")
        if timezone.replace('_', ' ').lower().startswith(location):
            appending = timezone[len(f'{location}/'):].replace('_', ' ').lower()
            if '/' not in appending:
                timezones[location].append(appending)

with open('timezones.json', 'w') as file:
    json.dump(timezones, file, indent=4)
