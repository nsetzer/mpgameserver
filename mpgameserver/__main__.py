import os
import sys
import argparse
from mpgameserver import EllipticCurvePrivateKey, EllipticCurvePublicKey


class Command(object):

    name = None
    aliases = []
    subcli = []

    def __init__(self):
        super(Command, self).__init__()

    def register(self, parser):

        kwargs = {}
        if self.aliases:
            kwargs['aliases'] = self.aliases

        help = self.__doc__ or ""
        help = help.replace("\n    ", "\n")
        kwargs['help'] = help.strip().split("\n")[0]
        kwargs['description'] = help.strip()


        subparser = parser.add_parser(self.name,
            formatter_class=argparse.RawTextHelpFormatter, **kwargs)
        subparser.set_defaults(_parser=subparser)

        if self.subcli:
            subsubparser = subparser.add_subparsers()

            for obj in self.subcli:
                obj.register(subsubparser)
        else:
            subparser.set_defaults(func=self.execute, cli=self)
            self.add_arguments(subparser)

    def add_arguments(self, subparser):
        pass

    def execute(self, args):
        pass


class GenerateKeyCommand(Command):
    """
    Generate a new Elliptic Curve key pair

    The output will be a private key (.key) and the corresponding public key (.pub)
    """
    name = "genkey"

    def add_arguments(self, subparser):

        subparser.add_argument("--name", type=str, default="root",
            help="the file name of the key")
        subparser.add_argument("outdir", type=str, help="where to write the PEM key to")

    def execute(self, args):

        prv_path = os.path.join(args.outdir, args.name + '.key')
        prvkey = EllipticCurvePrivateKey.new()
        with open(prv_path, "w") as wf:
            wf.write(prvkey.getPrivateKeyPEM())

        pub_path = os.path.join(args.outdir, args.name + '.pub')
        pubkey = prvkey.getPublicKey()
        with open(pub_path, "w") as wf:
            wf.write(pubkey.getPublicKeyPEM())


def main():

    parser = argparse.ArgumentParser(description='MpGameServer Utilities')
    subparser = parser.add_subparsers()

    GenerateKeyCommand().register(subparser)

    args = parser.parse_args()

    if args is None or not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    else:
        args.func(args)

if __name__ == '__main__':
    main()