# Color Temperature Light Mixer CW

Fork of [mion00/color-temperature-light-mixer](https://github.com/mion00/color-temperature-light-mixer) with a **max-at-CCT brightness scale** so Adaptive Lighting can request `2700K` and `90%` and both values stick.

Original integration by [@mion00](https://github.com/mion00). This fork keeps the same Home Assistant domain (`color_temperature_light_mixer`) so existing mixer devices can switch HACS source without being recreated.

## What this fork changes

The upstream mixer treats **100% brightness as both WW and CW full**. That physically forces a mixed color temperature (~3824K for 2700K/6500K strips). Adaptive Lighting always sends kelvin **and** brightness together, so evening `2700K` at high brightness becomes too cool.

**Prioritize color temperature** (default):

- Kelvin stays exact.
- 100% means the brightest mix **at that kelvin**.
- `2700K` with WW full and CW off **reports 100%**.
- AL `{color_temp_kelvin: 2700, brightness_pct: 90}` becomes WW at 90%, CW off, and still reports **2700K / 90%** — not 50%.

**Prioritize brightness** (upstream behavior):

- 100% is both channels full.
- High brightness may shift kelvin toward the midpoint.

Set the priority when adding a mixer, or later via **Configure** on the device.

## Install with HACS

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/chriswood1001/color-temperature-light-mixer-cw` as **Integration**
3. Download **Color Temperature Light Mixer CW**
4. Restart Home Assistant

If you already use the upstream mixer, do **not** delete the devices under Settings → Devices & Services. Download this fork so it overwrites `custom_components/color_temperature_light_mixer/`, then restart. Entity IDs stay the same.

## Credits

- Original integration: [mion00/color-temperature-light-mixer](https://github.com/mion00/color-temperature-light-mixer)
- Max-at-CCT mix described by [holasjuraj on issue #4](https://github.com/mion00/color-temperature-light-mixer/issues/4)
- Template-light inspiration: [gfrancesco/cwww-template-light-ha](https://github.com/gfrancesco/cwww-template-light-ha)

## License

MIT, same as the original project.
