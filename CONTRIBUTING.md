# Contributing

For Linux work, install the pinned tools and each application's native package
list per [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md); Ubuntu 24.04 is the CI
baseline and a Distrobox is optional. For normal work:

```sh
mise trust && mise install
(cd apps/zuko && mise trust && mise install)
eval "$(mise activate bash)"
just status
just check
```

## Work in the owning repository

This workspace coordinates independent Git histories:

- product behavior belongs in `apps/zuko`;
- reusable SDK, package, and plugin behavior belongs in its owning submodule;
- the parent owns exact pins, integration policy, and composed-build evidence.

Run commands from the child you are changing. Start with the narrowest relevant
check, then run that child's documented gate before updating the parent gitlink.
Do not copy child source or generated output into the parent.

## Before handing work off

- Keep each child change focused and reviewable in its own history.
- Confirm the child commit is public before asking the parent to pin it.
- Run `just check` and `just check-remotes` at the parent root.
- Record the exact child and composed-build commands that passed on Ubuntu
  24.04.
- Use native macOS or Windows for gates that require those platforms, and keep
  pinned release builders where their reproducibility is part of the test.

Follow [`docs/WORKFLOW.md`](docs/WORKFLOW.md) for child branches, upstream review
boundaries, pin updates, and recursive-clone proof. Dated evidence from another
Linux distribution is compatibility evidence; it does not change the supported
Ubuntu baseline.
