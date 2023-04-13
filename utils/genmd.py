#! cd .. && python utils/genmd.py

import os
import sys

sys.path.insert(0, os.getcwd())

import mpgameserver
import inspect
import types

def is_public_method(cls, attr):
    if attr.startswith('_'):
        return False

    value = getattr(cls, attr)

    return callable(value) and isinstance(value, types.FunctionType)

def is_static_method(cls, attr):
    if attr.startswith('_'):
        return False

    value = getattr(cls, attr)

    if inspect.isroutine(value):
        for o in inspect.getmro(cls):
            if attr in o.__dict__:
                bound_value = o.__dict__[attr]
                if isinstance(bound_value, staticmethod):
                    return True
    return False

def is_class_method(cls, attr):
    if attr.startswith('_'):
        return False

    value = getattr(cls, attr)

    if inspect.isroutine(value):
        for o in inspect.getmro(cls):
            if attr in o.__dict__:
                bound_value = o.__dict__[attr]
                if isinstance(bound_value, classmethod):
                    return True

    return False

def parse_doc(doc, markup='param'):

    if not doc:
        return "", {}, "", []

    tab = "  "

    summary = ""
    params = {}
    returns = ""

    paragraphs = [[]]

    code_block = False
    for src_line in doc.splitlines():

        if code_block:
            # collect all lines in the code block as is
            # until a terminator is found
            paragraphs[-1].append(src_line)
            if src_line.lstrip().startswith("```"):
                code_block = False
                paragraphs.append([])
            continue

        line = src_line.strip()
        if line:
            if line.startswith(":") and paragraphs[-1]:
                # part of parameter or attribute documentation
                paragraphs.append([])
                paragraphs[-1].append(line)
            elif line.startswith("|"):
                # part of a table
                paragraphs.append([])
                paragraphs[-1].append(line)
            elif line.startswith("```"):
                # beginning of a code block
                code_block = True
                paragraphs.append([])
                paragraphs[-1].append(src_line)
            else:
                paragraphs[-1].append(line)
        else:
            if paragraphs[-1]:
                paragraphs.append([])

    i = 0;
    while i < len(paragraphs):
        paragraph = paragraphs[i]

        if not paragraph:
            i += 1
            continue

        if paragraph[0].lstrip().startswith("```"):
            body = '\n'.join(paragraph)
            paragraph.clear()
            paragraph.append(body)
            i += 1

        elif paragraph[0].startswith(":%s" % markup):
            for j, line in enumerate(paragraph):
                if line.strip().startswith("*"):
                    paragraph[j] = '\n%s%s' % (tab, tab) + line

            text = ' '.join(paragraph)
            text = text[len(":%s" % markup):]
            name, text = text.split(':', 1)
            params[name.strip()] = text.strip()
            paragraphs.pop(i)
        elif paragraph[0].startswith(":return"):
            # parse
            # ":return x : y"
            # ":return: y"
            # ":returns: y"
            # yield y as a decscription of the return value
            text = ' '.join(paragraph)
            text = text[len(":return"):]
            name, text = text.split(':', 1)
            returns = text.strip()
            paragraphs.pop(i)
        elif not summary and not paragraph[0].strip().startswith("|"):
            # paragraph that is not a param def
            # and not a table def
            summary = ' '.join(paragraph)
            paragraphs.pop(i)
        else:
            i += 1

    return summary, params, returns, paragraphs

def genmd_function(stream, fn, name=None):
    tab = "  "

    if name is None:
        name = fn.__name__

    # * **`getPrivateKeyPEM()`** - return a string representation of the key
    spec = inspect.getfullargspec(fn)
    sig = inspect.signature(fn)
    summary, params, returns, body = parse_doc(fn.__doc__)

    if summary.startswith('private '):
        sys.stderr.write('ignoring private function %s\n' % name)
        return

    stream.write("* :small_blue_diamond: **`%s`**`%s` - %s\n" % (name, sig, summary))

    for name, param in sig.parameters.items():
        if name == 'self':
            continue

        stream.write("\n%s* **:arrow_forward: `%s:`** %s\n" % (tab, name, params.get(name, "")))

    if returns:
        stream.write("\n%s* **:leftwards_arrow_with_hook: `%s:`** %s\n" % (tab, 'returns', returns))

    if body:
        stream.write("\n")
        for para in body:
            para_text = ' '.join(para)
            if "```" in para_text:
                stream.write(para_text)
                stream.write("\n\n")
            else:
                stream.write("%s%s\n\n" % (tab, para_text))

def genmd_cls_method(stream, cls, attr):

    tab = "  "
    # * **`getPrivateKeyPEM()`** - return a string representation of the key
    #print("%s.%s" % (cls.__name__, attr))
    method = getattr(cls, attr)
    spec = inspect.getfullargspec(method)
    sig = inspect.signature(method)
    summary, params, returns, body = parse_doc(method.__doc__)

    if summary.startswith('private '):
        sys.stderr.write('ignoring private method %s of class %s\n' % (attr, cls.__name__))
        return

    name = cls.__name__ if attr == '__init__' else method.__name__

    stream.write("* :small_blue_diamond: **`%s`**`%s` - %s\n" % (name, sig, summary))

    for name, param in sig.parameters.items():
        if name == 'self':
            continue

        #anno = ""
        #if isinstance(param.annotation, str):
        #    anno = param.annotation
        #elif param.annotation is inspect._empty:
        #    pass
        #elif hasattr(param.annotation, __name__):
        #    anno = param.annotation.__name__
        #elif hasattr(param, __name__):
        #    anno = param.__name__
        #else:
        #    raise TypeError(param.annotation)

        stream.write("\n%s* **:arrow_forward: `%s:`** %s\n" % (tab, name, params.get(name, "")))

    if returns:
        stream.write("\n%s* **:leftwards_arrow_with_hook: `%s:`** %s\n" % (tab, 'returns', returns))

    if body:
        stream.write("\n")
        for para in body:
            stream.write("%s%s\n\n" % (tab, ' '.join(para)))

def genmd_cls(stream, cls, name=None, cls_vars=None):
    """
    summary
    summary2

    :param cls: woah
    budy

    body
    """
    stream.write("---\n")
    if name:
        # stream.write("## :large_blue_diamond: %s\n" % name)
        stream.write("## %s\n" % name)
    else:
        #stream.write("## :large_blue_diamond: %s\n" % cls.__name__)
        stream.write("## %s\n" % cls.__name__)
    summary, attrs, _, body = parse_doc(cls.__doc__, 'attr')

    stream.write("%s\n\n" % summary)

    _prev_table = False
    for para in body:
        text = ' '.join(para)
        _table = text.startswith("|")


        if not _table and _prev_table:
            stream.write('\n')

        stream.write(text)

        if _table:
            stream.write('\n')
        else:
            stream.write('\n\n')
        _prev_table = _table

    if cls_vars is None:
        cls_vars = vars(cls)

    if "__init__" in cls_vars:
        doc = cls.__init__.__doc__ or ""
        if not doc.strip().startswith('private'):
            stream.write("\n#### Constructor:\n\n")
            genmd_cls_method(stream, cls, "__init__")

    if attrs:
        stream.write("\n#### Public Attributes:\n\n")
        for name, text in sorted(attrs.items()):
            stream.write("**`%s`**: %s\n\n" % (name, text))


    tab = "  "

    meths = [ attr for attr in cls_vars \
        if is_class_method(cls, attr) ]

    if meths:
        stream.write("\n#### Class Methods:\n\n")
        for attr in sorted(meths):
            genmd_cls_method(stream, cls, attr)

    meths = [ attr for attr in cls_vars \
        if is_public_method(cls, attr) and is_static_method(cls, attr) ]

    if meths:
        stream.write("\n#### Static Methods:\n\n")
        for attr in sorted(meths):
            genmd_cls_method(stream, cls, attr)


    meths = [ attr for attr in cls_vars \
        if is_public_method(cls, attr) and not is_static_method(cls, attr) ]

    if meths:
        stream.write("\n#### Methods:\n\n")

        for attr in sorted(meths):
            genmd_cls_method(stream, cls, attr)

def genmd_enum(stream, cls, name=None, cls_vars=None):
    stream.write("---\n")
    if name:
        stream.write("## :large_orange_diamond: %s\n" % name)
    else:
        stream.write("## :large_orange_diamond: %s\n" % cls.__name__)
    summary, attrs, _, body = parse_doc(cls.__doc__, 'attr')

    stream.write("%s\n\n" % summary)

    for para in body:
        stream.write(' '.join(para))
        stream.write('\n\n')

    if cls_vars is None:
        cls_vars = vars(cls)

    stream.write("| Attribute | Enum Value | Description |\n")
    stream.write("| :-------- | ---------: | :---------- |\n")
    if hasattr(cls, '_name2value'):
        for attr, value in sorted(cls._name2value.items(), key=lambda x: x[1]):
            desc = attrs.get(attr, "")
            stream.write("| %s | %s | %s |\n" % (attr, value, desc))

def genmd_index(wf, classes=[], enums=[], functions=[]):
    for cls, name, *rest in classes:
        if name is None:
            name = cls.__name__
        wf.write("* [%s](#%s)\n" %(name, name.lower()))

    for cls, name in enums:
        if name is None:
            name = cls.__name__
        wf.write("* [%s](#%s)\n" %(name, name.lower()))

    for fn, name in functions:
        if name is None:
            name = fn.__name__
        wf.write("* [%s](#%s)\n" %(name, name.lower()))


def md_server():

    cls_vars = list(vars(mpgameserver.connection.ServerClientConnection))
    cls_vars.remove("__init__")
    cls_vars.append("send")

    servers = [
        (mpgameserver.handler.EventHandler, None),
        (mpgameserver.connection.ServerClientConnection, 'EventHandler.Client', cls_vars),
        (mpgameserver.context.ServerContext, None),
        (mpgameserver.twisted.TwistedServer, None),
        (mpgameserver.guiserver.GuiServer, None),
    ]

    enums = [
        (mpgameserver.connection.ConnectionStatus, None),
        (mpgameserver.connection.RetryMode, None),
    ]

    with open("docs/server.md", "w") as wf:
        wf.write("[Home](../README.md)\n\n")
        wf.write("\n")
        wf.write(mpgameserver.server.__doc__)
        wf.write("\n")

        genmd_index(wf, servers, enums)

        #wf.write("\n---\n\nThere is currently two supported implementations of the server. A Headless implementation (no ui) or with a PyGame interface for metrics\n\n")
        for args in servers:
            genmd_cls(wf, *args)
        for cls, name in enums:
            genmd_enum(wf, cls, name)

def md_client():

    classes = [
        (mpgameserver.client.UdpClient, None),
        (mpgameserver.connection.ConnectionStats, None),
    ]
    enums = [
        (mpgameserver.connection.ConnectionStatus, None),
        (mpgameserver.connection.RetryMode, None),
    ]

    with open("docs/client.md", "w") as wf:
        wf.write("[Home](../README.md)\n\n")
        wf.write("\n")
        wf.write(mpgameserver.client.__doc__)
        wf.write("\n")

        genmd_index(wf, classes, enums)

        for cls, name in classes:
            genmd_cls(wf, cls, name)
        for cls, name in enums:
            genmd_enum(wf, cls, name)

def md_network():


    classes = [
        (mpgameserver.connection.SeqNum, None),
        (mpgameserver.connection.BitField, None),
        (mpgameserver.connection.PacketHeader, None),
        (mpgameserver.connection.Packet, None),
        (mpgameserver.connection.PendingMessage, None),
    ]
    enums = [
        (mpgameserver.connection.PacketIdentifier, None),
        (mpgameserver.connection.PacketType, None),
        (mpgameserver.connection.ConnectionStatus, None),
        (mpgameserver.connection.RetryMode, None),
    ]
    with open("docs/network.md", "w") as wf:
        wf.write("[Home](../README.md)\n\n")
        wf.write("\n")
        wf.write(mpgameserver.connection.__doc__)
        wf.write("\n")

        genmd_index(wf, classes, enums)

        for cls, name in classes:
            genmd_cls(wf, cls, name)
        for cls, name in enums:
            genmd_enum(wf, cls, name)

def md_serializable():

    classes = [
        (mpgameserver.serializable.SerializableType, None),
        (mpgameserver.serializable.Serializable, None),
        (mpgameserver.serializable.SerializableEnum, None),
    ]
    with open("docs/serializable.md", "w") as wf:
        wf.write("[Home](../README.md)\n\n")
        wf.write(mpgameserver.serializable.__doc__)
        wf.write("\n")

        genmd_index(wf, classes)

        for cls, name in classes:
            genmd_cls(wf, cls, name)

def md_crypto():


    classes = [
        (mpgameserver.crypto.EllipticCurvePrivateKey, None),
        (mpgameserver.crypto.EllipticCurvePublicKey, None),
    ]
    with open("docs/crypto.md", "w") as wf:
        wf.write("[Home](../README.md)\n\n")
        wf.write("\n")
        wf.write(mpgameserver.crypto.__doc__)
        wf.write("\n")

        genmd_index(wf, classes)

        for cls, name in classes:
            genmd_cls(wf, cls, name)

def md_misc():

    doc = """
    # Utility Classes

    """.replace("\n    ", "")

    classes = [
        (mpgameserver.timer.Timer, None),
        (mpgameserver.graph.LineGraph, None),
        (mpgameserver.graph.AreaGraph, None),
    ]
    with open("docs/misc.md", "w") as wf:
        wf.write("[Home](../README.md)\n\n")
        wf.write("\n")
        wf.write(doc)
        wf.write("\n")

        genmd_index(wf, classes)

        for cls, name in classes:
            genmd_cls(wf, cls, name)

def md_http():

    doc = """
    # HTTP/TCP Protocol



    """.replace("\n    ", "")

    classes = [
        (mpgameserver.http_server.Resource, None),
        (mpgameserver.http_server.Request, None),
        (mpgameserver.http_server.Router, None),
        (mpgameserver.http_server.Response, None),
        (mpgameserver.http_server.ErrorResponse, None),
        (mpgameserver.http_server.JsonResponse, None),
        (mpgameserver.http_server.SerializableResponse, None),
        (mpgameserver.http_server.HTTPServer, None),
        (mpgameserver.http_client.HTTPClient, None),
    ]
    enums=[]
    functions = [
        (mpgameserver.http_server.path_join_safe, None),
    ]
    with open("docs/http.md", "w") as wf:
        wf.write("[Home](../README.md)\n\n")
        wf.write("\n")
        wf.write(doc)
        wf.write("\n")

        genmd_index(wf, classes, enums, functions)

        for cls, name in classes:
            genmd_cls(wf, cls, name)

        wf.write("\n## :cherry_blossom: Functions:\n\n")
        for fn, name in functions:
            genmd_function(wf, fn, name)


def md_event_dispatch():

    doc = """
    # Event Dispatch API

    The Event Dispatch API is a collection of classes designed to work
    with the serialization library. It allows for message dispatch
    based on the type of the message.
    It can be used in both the server or client.

    """.replace("\n    ", " ")

    cls_vars = [
        "__init__",
        "register",
        "unregister",
        "register_function",
        "unregister_function",
        "dispatch",
    ]

    classes = [
        (mpgameserver.dispatch.ServerMessageDispatcher, None, cls_vars),
        (mpgameserver.dispatch.ClientMessageDispatcher, None, cls_vars),
    ]
    functions = [
        (mpgameserver.dispatch.server_event, None),
        (mpgameserver.dispatch.client_event, None),
    ]
    with open("docs/event_dispatch.md", "w") as wf:
        wf.write("[Home](../README.md)\n")
        genmd_index(wf, classes)
        wf.write("\n")
        wf.write(doc)
        wf.write("\n")
        for cls, name, vars in classes:
            genmd_cls(wf, cls, name, vars)

        wf.write("\n## :cherry_blossom: Functions:\n\n")
        for fn, name in functions:
            genmd_function(wf, fn, name)

def md_experimental():

    doc = """
    # Experimental Modules

    The classes documented here are experimental and may have breaking API changes in the future.


    """.replace("\n    ", "")

    classes = [
        (mpgameserver.task.TaskPool, None),
        (mpgameserver.captcha.Captcha, None),
        (mpgameserver.auth.Auth, None),
    ]
    with open("docs/experimental.md", "w") as wf:
        wf.write("[Home](../README.md)\n")
        genmd_index(wf, classes)
        wf.write("\n")
        wf.write(doc)
        wf.write("\n")
        for cls, name in classes:
            genmd_cls(wf, cls, name)

def md_engine():

    doc = """
    # Pygame Engine

    """.replace("\n    ", "")





    engine_intro = """
        ## Pygame Engine
    """.replace("\n    ", "")

    engine = [
        (mpgameserver.pylon.GameScene, None),
        (mpgameserver.pylon.Engine, None),
    ]

    input_intro = """
        ## Network Synchronized Objects


    """.replace("\n    ", "")

    user_input = [
        (mpgameserver.pylon.KeyboardInputDevice, None),
        (mpgameserver.pylon.JoystickInputDevice, None),
        (mpgameserver.pylon.NetworkPlayerState, None),
        (mpgameserver.pylon.InputController, None),
        (mpgameserver.pylon.RemoteInputController, None),
    ]

    entity_intro = """
        ## User Input


    """.replace("\n    ", "")

    components = [
        (mpgameserver.pylon.Entity, None),
        (mpgameserver.pylon.Physics2dComponent, None),
        (mpgameserver.pylon.PlatformPhysics2dComponent, None),
        (mpgameserver.pylon.AdventurePhysics2dComponent, None),
        (mpgameserver.pylon.AnimationComponent, None),
    ]

    with open("docs/engine.md", "w") as wf:
        wf.write("[Home](../README.md)\n")

        genmd_index(wf, engine + user_input + components)

        wf.write("\n")
        wf.write(doc)
        wf.write("\n")

        wf.write("\n")
        wf.write(engine_intro)
        wf.write("\n")

        for cls, name in engine:
            genmd_cls(wf, cls, name)

        wf.write("\n")
        wf.write(input_intro)
        wf.write("\n")

        for cls, name in user_input:
            genmd_cls(wf, cls, name)

        wf.write("\n")
        wf.write(entity_intro)
        wf.write("\n")

        for cls, name in components:
            genmd_cls(wf, cls, name)

def main():

    md_server()
    md_client()
    md_network()
    md_serializable()
    md_crypto()
    md_misc()
    md_event_dispatch()
    md_experimental()
    md_http()
    md_engine()

if __name__ == '__main__':
    main()
