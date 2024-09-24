# FPVM workshop examples

This repository contains model evolution examples that have been used to demonstrate the Munidiff timeline explorer.

- Explorer's website: https://munidiff.github.io
- Explorer's repository: https://github.com/munidiff/munidiff.github.io

## Accepted url types

### Repository url

Providing the explorer with a url to a GitHub repository allows seeing a list of recent commits on the left-hand side. By clicking on the title of any of these commits, the models that contained changes are listed and can be further inspected.

**Try it**: paste the following link in the explorer's input: https://github.com/munidiff/fpvm-examples

You can also simply click into the following link to the explorer, which contains the previous url as a parameter: https://munidiff.github.io/?url=https://github.com/munidiff/fpvm-examples

### Commit url

Providing a url pointing to a concrete commit automatically loads the details of that commit (apart from the list of commits).

The following links show the details of commits with model changes:

- Update `description` of a `Job` and add a `Status` element https://munidiff.github.io/?url=https://github.com/alfonsodelavega/modiff/commit/c6b3418f4ec71c329f06fab594b526f41cb687bf

- Simple property change in a metamodel: https://munidiff.github.io/?url=https://github.com/eclipse/epsilon/commit/033c409351e4d35c8bb0bd50f20addec7d72d034

### File url

If a file url is provided, the commits listed on the left-hand side are only those where the file received some changes. The details of the latest commit affecting the file are automatically loaded.

Examples of urls to concrete files:

- `repairshop.model` commits: https://munidiff.github.io/?url=https://github.com/munidiff/fpvm-examples/blob/main/models/repairshop.model

- Changes to the metamodel of [Epsilon Picto's sequence diagram example](https://eclipse.dev/epsilon/doc/articles/picto-sequence-diagrams/): https://munidiff.github.io/?url=https://github.com/eclipse/epsilon/blob/main/examples/org.eclipse.epsilon.examples.picto.plantuml.minisd/minisd.ecore

- Evolution of the `dom.ecore` metamodel that is used internally by [Picto](https://www.eclipse.org/epsilon/doc/picto/): https://munidiff.github.io/?url=https://github.com/eclipse/epsilon/commits/main/plugins/org.eclipse.epsilon.picto/src/org/eclipse/epsilon/picto/dom/dom.ecore
