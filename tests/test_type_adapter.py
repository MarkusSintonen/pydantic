import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, ForwardRef, Generic, List, NamedTuple, Optional, Tuple, TypeVar, Union

import pytest
from pydantic_core import ValidationError
from typing_extensions import Annotated, Literal, TypeAlias, TypedDict, get_args

from pydantic import BaseModel, Field, TypeAdapter, ValidationInfo, create_model, field_validator
from pydantic._internal import _typing_extra
from pydantic.config import ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.errors import PydanticUserError

ItemType = TypeVar('ItemType')

NestedList = List[List[ItemType]]

DEFER_ENABLE_MODE = ('model', 'type_adapter')


class PydanticModel(BaseModel):
    x: int


T = TypeVar('T')


class GenericPydanticModel(BaseModel, Generic[T]):
    x: NestedList[T]


class SomeTypedDict(TypedDict):
    x: int


class SomeNamedTuple(NamedTuple):
    x: int


@pytest.mark.parametrize(
    'tp, val, expected',
    [
        (PydanticModel, PydanticModel(x=1), PydanticModel(x=1)),
        (PydanticModel, {'x': 1}, PydanticModel(x=1)),
        (SomeTypedDict, {'x': 1}, {'x': 1}),
        (SomeNamedTuple, SomeNamedTuple(x=1), SomeNamedTuple(x=1)),
        (List[str], ['1', '2'], ['1', '2']),
        (Tuple[str], ('1',), ('1',)),
        (Tuple[str, int], ('1', 1), ('1', 1)),
        (Tuple[str, ...], ('1',), ('1',)),
        (Dict[str, int], {'foo': 123}, {'foo': 123}),
        (Union[int, str], 1, 1),
        (Union[int, str], '2', '2'),
        (GenericPydanticModel[int], {'x': [[1]]}, GenericPydanticModel[int](x=[[1]])),
        (GenericPydanticModel[int], {'x': [['1']]}, GenericPydanticModel[int](x=[[1]])),
        (NestedList[int], [[1]], [[1]]),
        (NestedList[int], [['1']], [[1]]),
    ],
)
def test_types(tp: Any, val: Any, expected: Any):
    v = TypeAdapter(tp).validate_python
    assert expected == v(val)


IntList = List[int]
OuterDict = Dict[str, 'IntList']


@pytest.mark.parametrize('defer_build', [False, True])
def test_global_namespace_variables(defer_build: bool):
    config = ConfigDict(defer_build=True, _defer_build_mode=DEFER_ENABLE_MODE) if defer_build else None

    v = TypeAdapter(OuterDict, config=config).validate_python
    res = v({'foo': [1, '2']})
    assert res == {'foo': [1, 2]}


@pytest.mark.parametrize('defer_build', [False, True])
def test_local_namespace_variables(defer_build: bool):
    config = ConfigDict(defer_build=True, _defer_build_mode=DEFER_ENABLE_MODE) if defer_build else None

    IntList = List[int]  # noqa: F841
    OuterDict = Dict[str, 'IntList']

    v = TypeAdapter(OuterDict, config=config).validate_python

    res = v({'foo': [1, '2']})
    assert res == {'foo': [1, 2]}


@pytest.mark.skipif(sys.version_info < (3, 9), reason="ForwardRef doesn't accept module as a parameter in Python < 3.9")
def test_top_level_fwd_ref():
    FwdRef = ForwardRef('OuterDict', module=__name__)
    v = TypeAdapter(FwdRef).validate_python

    res = v({'foo': [1, '2']})
    assert res == {'foo': [1, 2]}


MyUnion: TypeAlias = 'Union[str, int]'


def test_type_alias():
    MyList = List[MyUnion]
    v = TypeAdapter(MyList).validate_python
    res = v([1, '2'])
    assert res == [1, '2']


def test_validate_python_strict() -> None:
    class Model(TypedDict):
        x: int

    class ModelStrict(Model):
        __pydantic_config__ = ConfigDict(strict=True)  # type: ignore

    lax_validator = TypeAdapter(Model)
    strict_validator = TypeAdapter(ModelStrict)

    assert lax_validator.validate_python({'x': '1'}, strict=None) == Model(x=1)
    assert lax_validator.validate_python({'x': '1'}, strict=False) == Model(x=1)
    with pytest.raises(ValidationError) as exc_info:
        lax_validator.validate_python({'x': '1'}, strict=True)
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('x',), 'msg': 'Input should be a valid integer', 'input': '1'}
    ]

    with pytest.raises(ValidationError) as exc_info:
        strict_validator.validate_python({'x': '1'})
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('x',), 'msg': 'Input should be a valid integer', 'input': '1'}
    ]
    assert strict_validator.validate_python({'x': '1'}, strict=False) == Model(x=1)
    with pytest.raises(ValidationError) as exc_info:
        strict_validator.validate_python({'x': '1'}, strict=True)
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('x',), 'msg': 'Input should be a valid integer', 'input': '1'}
    ]


@pytest.mark.xfail(reason='Need to fix this in https://github.com/pydantic/pydantic/pull/5944')
def test_validate_json_strict() -> None:
    class Model(TypedDict):
        x: int

    class ModelStrict(Model):
        __pydantic_config__ = ConfigDict(strict=True)  # type: ignore

    lax_validator = TypeAdapter(Model, config=ConfigDict(strict=False))
    strict_validator = TypeAdapter(ModelStrict)

    assert lax_validator.validate_json(json.dumps({'x': '1'}), strict=None) == Model(x=1)
    assert lax_validator.validate_json(json.dumps({'x': '1'}), strict=False) == Model(x=1)
    with pytest.raises(ValidationError) as exc_info:
        lax_validator.validate_json(json.dumps({'x': '1'}), strict=True)
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('x',), 'msg': 'Input should be a valid integer', 'input': '1'}
    ]

    with pytest.raises(ValidationError) as exc_info:
        strict_validator.validate_json(json.dumps({'x': '1'}), strict=None)
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('x',), 'msg': 'Input should be a valid integer', 'input': '1'}
    ]
    assert strict_validator.validate_json(json.dumps({'x': '1'}), strict=False) == Model(x=1)
    with pytest.raises(ValidationError) as exc_info:
        strict_validator.validate_json(json.dumps({'x': '1'}), strict=True)
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('x',), 'msg': 'Input should be a valid integer', 'input': '1'}
    ]


def test_validate_python_context() -> None:
    contexts: List[Any] = [None, None, {'foo': 'bar'}]

    class Model(BaseModel):
        x: int

        @field_validator('x')
        def val_x(cls, v: int, info: ValidationInfo) -> int:
            assert info.context == contexts.pop(0)
            return v

    validator = TypeAdapter(Model)
    validator.validate_python({'x': 1})
    validator.validate_python({'x': 1}, context=None)
    validator.validate_python({'x': 1}, context={'foo': 'bar'})
    assert contexts == []


def test_validate_json_context() -> None:
    contexts: List[Any] = [None, None, {'foo': 'bar'}]

    class Model(BaseModel):
        x: int

        @field_validator('x')
        def val_x(cls, v: int, info: ValidationInfo) -> int:
            assert info.context == contexts.pop(0)
            return v

    validator = TypeAdapter(Model)
    validator.validate_json(json.dumps({'x': 1}))
    validator.validate_json(json.dumps({'x': 1}), context=None)
    validator.validate_json(json.dumps({'x': 1}), context={'foo': 'bar'})
    assert contexts == []


def test_validate_python_from_attributes() -> None:
    class Model(BaseModel):
        x: int

    class ModelFromAttributesTrue(Model):
        model_config = ConfigDict(from_attributes=True)

    class ModelFromAttributesFalse(Model):
        model_config = ConfigDict(from_attributes=False)

    @dataclass
    class UnrelatedClass:
        x: int = 1

    input = UnrelatedClass(1)

    ta = TypeAdapter(Model)

    for from_attributes in (False, None):
        with pytest.raises(ValidationError) as exc_info:
            ta.validate_python(UnrelatedClass(), from_attributes=from_attributes)
        assert exc_info.value.errors(include_url=False) == [
            {
                'type': 'model_type',
                'loc': (),
                'msg': 'Input should be a valid dictionary or instance of Model',
                'input': input,
                'ctx': {'class_name': 'Model'},
            }
        ]

    res = ta.validate_python(UnrelatedClass(), from_attributes=True)
    assert res == Model(x=1)

    ta = TypeAdapter(ModelFromAttributesTrue)

    with pytest.raises(ValidationError) as exc_info:
        ta.validate_python(UnrelatedClass(), from_attributes=False)
    assert exc_info.value.errors(include_url=False) == [
        {
            'type': 'model_type',
            'loc': (),
            'msg': 'Input should be a valid dictionary or instance of ModelFromAttributesTrue',
            'input': input,
            'ctx': {'class_name': 'ModelFromAttributesTrue'},
        }
    ]

    for from_attributes in (True, None):
        res = ta.validate_python(UnrelatedClass(), from_attributes=from_attributes)
        assert res == ModelFromAttributesTrue(x=1)

    ta = TypeAdapter(ModelFromAttributesFalse)

    for from_attributes in (False, None):
        with pytest.raises(ValidationError) as exc_info:
            ta.validate_python(UnrelatedClass(), from_attributes=from_attributes)
        assert exc_info.value.errors(include_url=False) == [
            {
                'type': 'model_type',
                'loc': (),
                'msg': 'Input should be a valid dictionary or instance of ModelFromAttributesFalse',
                'input': input,
                'ctx': {'class_name': 'ModelFromAttributesFalse'},
            }
        ]

    res = ta.validate_python(UnrelatedClass(), from_attributes=True)
    assert res == ModelFromAttributesFalse(x=1)


@pytest.mark.parametrize(
    'field_type,input_value,expected,raises_match,strict',
    [
        (bool, 'true', True, None, False),
        (bool, 'true', True, None, True),
        (bool, 'false', False, None, False),
        (bool, 'e', ValidationError, 'type=bool_parsing', False),
        (int, '1', 1, None, False),
        (int, '1', 1, None, True),
        (int, 'xxx', ValidationError, 'type=int_parsing', True),
        (float, '1.1', 1.1, None, False),
        (float, '1.10', 1.1, None, False),
        (float, '1.1', 1.1, None, True),
        (float, '1.10', 1.1, None, True),
        (date, '2017-01-01', date(2017, 1, 1), None, False),
        (date, '2017-01-01', date(2017, 1, 1), None, True),
        (date, '2017-01-01T12:13:14.567', ValidationError, 'type=date_from_datetime_inexact', False),
        (date, '2017-01-01T12:13:14.567', ValidationError, 'type=date_parsing', True),
        (date, '2017-01-01T00:00:00', date(2017, 1, 1), None, False),
        (date, '2017-01-01T00:00:00', ValidationError, 'type=date_parsing', True),
        (datetime, '2017-01-01T12:13:14.567', datetime(2017, 1, 1, 12, 13, 14, 567_000), None, False),
        (datetime, '2017-01-01T12:13:14.567', datetime(2017, 1, 1, 12, 13, 14, 567_000), None, True),
    ],
    ids=repr,
)
def test_validate_strings(field_type, input_value, expected, raises_match, strict):
    ta = TypeAdapter(field_type)
    if raises_match is not None:
        with pytest.raises(expected, match=raises_match):
            ta.validate_strings(input_value, strict=strict)
    else:
        assert ta.validate_strings(input_value, strict=strict) == expected


@pytest.mark.parametrize('strict', [True, False])
def test_validate_strings_dict(strict):
    assert TypeAdapter(Dict[int, date]).validate_strings({'1': '2017-01-01', '2': '2017-01-02'}, strict=strict) == {
        1: date(2017, 1, 1),
        2: date(2017, 1, 2),
    }


def test_annotated_type_disallows_config() -> None:
    class Model(BaseModel):
        x: int

    with pytest.raises(PydanticUserError, match='Cannot use `config`'):
        TypeAdapter(Annotated[Model, ...], config=ConfigDict(strict=False))


def test_ta_config_with_annotated_type() -> None:
    class TestValidator(BaseModel):
        x: str

        model_config = ConfigDict(str_to_lower=True)

    assert TestValidator(x='ABC').x == 'abc'
    assert TypeAdapter(TestValidator).validate_python({'x': 'ABC'}).x == 'abc'
    assert TypeAdapter(Annotated[TestValidator, ...]).validate_python({'x': 'ABC'}).x == 'abc'

    class TestSerializer(BaseModel):
        some_bytes: bytes
        model_config = ConfigDict(ser_json_bytes='base64')

    result = TestSerializer(some_bytes=b'\xaa')
    assert result.model_dump(mode='json') == {'some_bytes': 'qg=='}
    assert TypeAdapter(TestSerializer).dump_python(result, mode='json') == {'some_bytes': 'qg=='}

    # cases where SchemaSerializer is constructed within TypeAdapter's __init__
    assert TypeAdapter(Annotated[TestSerializer, ...]).dump_python(result, mode='json') == {'some_bytes': 'qg=='}
    assert TypeAdapter(Annotated[List[TestSerializer], ...]).dump_python([result], mode='json') == [
        {'some_bytes': 'qg=='}
    ]


def test_eval_type_backport():
    v = TypeAdapter('list[int | str]').validate_python
    assert v([1, '2']) == [1, '2']
    with pytest.raises(ValidationError) as exc_info:
        v([{'not a str or int'}])
    # insert_assert(exc_info.value.errors(include_url=False))
    assert exc_info.value.errors(include_url=False) == [
        {
            'type': 'int_type',
            'loc': (0, 'int'),
            'msg': 'Input should be a valid integer',
            'input': {'not a str or int'},
        },
        {
            'type': 'string_type',
            'loc': (0, 'str'),
            'msg': 'Input should be a valid string',
            'input': {'not a str or int'},
        },
    ]
    with pytest.raises(ValidationError) as exc_info:
        v('not a list')
    # insert_assert(exc_info.value.errors(include_url=False))
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'list_type', 'loc': (), 'msg': 'Input should be a valid list', 'input': 'not a list'}
    ]


def defer_build_test_type_adapters(
    defer_build: bool, defer_build_mode: Tuple[Literal['model', 'type_adapter'], ...]
) -> List[TypeAdapter]:
    class Model(BaseModel, defer_build=defer_build, _defer_build_mode=defer_build_mode):
        x: int

    class SubModel(Model):
        y: Optional[int] = None

    @pydantic_dataclass(config=ConfigDict(defer_build=defer_build, _defer_build_mode=defer_build_mode))
    class DataClassModel:
        x: int

    @pydantic_dataclass
    class SubDataClassModel(DataClassModel):
        y: Optional[int] = None

    class TypedDictModel(TypedDict):
        __pydantic_config__ = ConfigDict(defer_build=defer_build, _defer_build_mode=defer_build_mode)  # type: ignore
        x: int

    models = [
        (Model, None),
        (SubModel, None),
        (create_model('DynamicModel', __base__=Model), None),
        (create_model('DynamicSubModel', __base__=SubModel), None),
        (DataClassModel, None),
        (SubDataClassModel, None),
        (TypedDictModel, None),
        (Dict[str, int], ConfigDict(defer_build=defer_build, _defer_build_mode=defer_build_mode)),
    ]
    models = [
        *models,
        # FastAPI heavily uses Annotated so test that as well
        *[(Annotated[model, Field(title='abc')], config) for model, config in models],
    ]
    return [TypeAdapter(model, config=config) for model, config in models]


@pytest.mark.parametrize('defer_build', [False, True])
@pytest.mark.parametrize('defer_build_mode', [('model',), DEFER_ENABLE_MODE])
def test_core_schema_respects_defer_build(
    defer_build: bool,
    defer_build_mode: Tuple[Literal['model', 'type_adapter'], ...],
) -> None:
    for type_adapter in defer_build_test_type_adapters(defer_build, defer_build_mode):
        if defer_build and 'type_adapter' in defer_build_mode:
            assert 'core_schema' not in type_adapter.__dict__, 'Should be built deferred via cached_property'
        else:
            assert type_adapter.__dict__.get('core_schema') is not None, 'Should be built before usage'

        json_schema = type_adapter.json_schema()  # Use it
        assert "'type': 'integer'" in str(json_schema)  # Sanity check

        assert type_adapter.__dict__.get('core_schema') is not None, 'Should be built after the usage'


@pytest.mark.parametrize('defer_build', [False, True])
@pytest.mark.parametrize('defer_build_mode', [('model',), DEFER_ENABLE_MODE])
def test_validator_respects_defer_build(
    defer_build: bool,
    defer_build_mode: Tuple[Literal['model', 'type_adapter'], ...],
) -> None:
    for type_adapter in defer_build_test_type_adapters(defer_build, defer_build_mode):
        if defer_build and 'type_adapter' in defer_build_mode:
            assert 'validator' not in type_adapter.__dict__, 'Should be built deferred via cached_property'
        else:
            assert type_adapter.__dict__.get('validator') is not None, 'Should be built before usage'

        validated = type_adapter.validate_python({'x': 1})  # Use it
        assert (validated['x'] if isinstance(validated, dict) else getattr(validated, 'x')) == 1  # Sanity check

        assert type_adapter.__dict__.get('validator') is not None, 'Should be built after the usage'


@pytest.mark.parametrize('defer_build', [False, True])
@pytest.mark.parametrize('defer_build_mode', [('model',), DEFER_ENABLE_MODE])
def test_serializer_respects_defer_build(
    defer_build: bool,
    defer_build_mode: Tuple[Literal['model', 'type_adapter'], ...],
) -> None:
    for type_adapter in defer_build_test_type_adapters(defer_build, defer_build_mode):
        type_ = type_adapter._type
        type_ = get_args(type_)[0] if _typing_extra.is_annotated(type_) else type_
        dumped = type_(x=1) if hasattr(type_, '__pydantic_complete__') else dict(x=1)

        if defer_build and 'type_adapter' in defer_build_mode:
            assert 'serializer' not in type_adapter.__dict__, 'Should be built deferred via cached_property'
        else:
            assert type_adapter.__dict__.get('serializer') is not None, 'Should be built before usage'

        raw = type_adapter.dump_json(dumped)  # Use it
        assert json.loads(raw.decode())['x'] == 1  # Sanity check

        assert type_adapter.__dict__.get('serializer') is not None, 'Should be built after the usage'
