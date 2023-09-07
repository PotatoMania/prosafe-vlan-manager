import click


class RequiredIf(click.Option):
    def __init__(self, *args, **kwargs):
        self.required_if = kwargs.pop('required_if')
        assert self.required_if, "'required_if' parameter required"
        kwargs['help'] = (kwargs.get('help', '') +
            ' NOTE: this argument is necessary when using "%s"' %
            self.required_if
        ).strip()
        super(RequiredIf, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        we_are_present = self.name in opts
        other_present = self.required_if in opts

        if other_present and not we_are_present:
            raise click.UsageError(
                "Illegal usage: `%s` is required when using `%s`" % (
                    self.name, self.required_if))

        return super(RequiredIf, self).handle_parse_result(
            ctx, opts, args)
