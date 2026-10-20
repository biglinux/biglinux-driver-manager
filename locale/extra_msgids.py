# Not run: strings xgettext collects for the big-driver-manager-cli catalog
# that the code does not mark itself.
# ruff: noqa


def _(text):
    return text


# argparse (Python 3.14) translates these through the global text domain,
# which big-drivers points at its own catalog (core.i18n.use_for_argparse).
_("usage: ")
_("positional arguments")
_("options")
_("show this help message and exit")
_("the following arguments are required: %s")
_("unrecognized arguments: %s")
_("invalid choice: %(value)r (choose from %(choices)s)")
_("argument %(argument_name)s: %(message)s")
_("not allowed with argument %s")
_("one of the arguments %s is required")
_("expected one argument")
_("ambiguous option: %(option)s could match %(matches)s")
_("%(prog)s: error: %(message)s\n")

# polkit (usr/share/polkit-1/actions/br.com.biglinux.drivermanager.cli.policy),
# written into the policy by scripts/update-translations.sh
_("Install or remove drivers, kernels and Mesa")
_("Authentication is required to install or remove drivers")
