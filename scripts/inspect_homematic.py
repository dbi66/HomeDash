import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.hmip_provider import HomematicProviderError, load_home


SKIP_ATTRIBUTES = {
    "id",
    "homeId",
    "device",
    "groups",
    "functionalChannels",
    "_connection",
    "_rawJSONData",
}


def scalar_attributes(value: object) -> list[str]:
    attributes = []
    for name in sorted(dir(value)):
        if name.startswith("_") or name in SKIP_ATTRIBUTES:
            continue
        try:
            attribute = getattr(value, name)
        except Exception:
            continue
        if isinstance(attribute, (str, int, float, bool)) or attribute is None:
            attributes.append(f"{name}={attribute}")
    return attributes


def main() -> int:
    try:
        home = load_home()
    except HomematicProviderError as error:
        print(f"Homematic IP inspection failed: {error}")
        return 1

    print(f"Connected: {home.connected}")
    print(f"Devices: {len(home.devices)}")
    print(f"Groups: {len(home.groups)}")
    print(f"Functional channels: {len(home.channels)}")
    print("\nRooms and available device data:")

    for group in home.groups:
        if getattr(group, "groupType", None) == "META":
            continue
        print(f"\n[{group.label}]")
        for device in getattr(group, "devices", []):
            print(f"  - {device.label} ({device.modelType}, {device.deviceType})")
            channel_types = sorted(
                str(channel.functionalChannelType)
                for channel in getattr(device, "functionalChannels", [])
            )
            if channel_types:
                print(f"    channels: {', '.join(channel_types)}")
            attributes = scalar_attributes(device)
            if attributes:
                print(f"    data: {', '.join(attributes)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
